"""Public Best Buy page collection using ordinary, sandboxed Chromium.

No API key, stealth patches, stored sessions, CAPTCHA solvers or private endpoints.
Site terms may restrict collection; access denials and login barriers stop the run.
"""
import os
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from pof.live.errors import SourceError, from_http
from pof.models import Product
from pof.product_evidence import catalog_labels, explicit_fields
from pof.security import MAX_RESPONSE, validate_url
from pof.browser import browser_env

HOST = "www.bestbuy.com"
LOCK = threading.Lock()
BROWSERS = Path(__file__).resolve().parents[2] / "data" / "browsers"


def browser_installed():
    return BROWSERS.exists() and any(BROWSERS.glob("chromium-*/chrome-win*/chrome.exe"))


def configure_browser_path():
    if BROWSERS.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))


def listing_url(query, page=1):
    terms = " ".join(value for value in (query.keywords, query.brand, query.model) if value)
    if not terms:
        terms = query.category_name or ""
    if not terms and query.category_id:
        terms = {"abcat0500000": "computer accessories", "abcat0204000": "headphones",
                 "abcat0101000": "television", "abcat0800000": "cell phone",
                 "abcat0900000": "home appliances"}.get(query.category_id, "electronics")
    if not terms and not query.category_id:
        return f"https://{HOST}/site/top-deals/pcmcat1563302966754.c?id=pcmcat1563302966754&intl=nosplash"
    # This is the public US-store preference also present on Best Buy's own
    # international page links; it is not an authentication/anti-bot token.
    params = {"id": "pcat17071", "st": terms or "*", "cp": page, "intl": "nosplash"}
    return f"https://{HOST}/site/searchpage.jsp?" + urlencode(params)


def money(text):
    # Accept one concrete displayed USD price, never price ranges or installment phrases.
    if re.search(r"/mo|per month|\bfrom\b|\bstarting\b", text, re.I):
        return None
    values = re.findall(r"\$\s*([\d,]+\.\d{2})(?!\d)", text)
    values = list(dict.fromkeys(values))
    if len(values) != 1:
        return None
    return float(values[0].replace(",", ""))


def read_graphql_only(payload):
    if not payload or len(payload) > 256000:
        return False
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return False
    operations = data if isinstance(data, list) else [data]
    if not 1 <= len(operations) <= 20:
        return False
    return all(isinstance(op, dict) and isinstance(op.get("query"), str)
               and bool(re.match(r"^\s*(query\b|\{)", op["query"]))
               and not re.search(r"\bmutation\b", op["query"], re.I) for op in operations)


def read_request_allowed(method, url, resource_type, count, post_data=None):
    target = urlsplit(url)
    forbidden = ("/identity", "/cart", "/checkout", "/account", "/profile", "/purchasehistory")
    read_method = method == "GET" or (method == "POST" and target.path == "/gateway/graphql" and read_graphql_only(post_data))
    return (read_method and resource_type in {"document", "script", "stylesheet", "xhr", "fetch"}
            and target.scheme == "https" and target.hostname == HOST and target.port in (None, 443)
            and not target.username and not target.password
            and not target.path.lower().startswith(forbidden) and count < 120)


def normalize_card(record, market="US"):
    url = urljoin(f"https://{HOST}", record.get("url", ""))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.username or parsed.password:
        raise ValueError("Invalid public listing URL")
    sku = record.get("sku") or parse_qs(parsed.query).get("skuId", [""])[0]
    if not sku:
        modern = re.search(r"/sku/(\d+)", parsed.path)
        sku = modern[1] if modern else ""
    if not sku:
        found = re.search(r"/(\d{5,10})\.p", parsed.path)
        sku = found[1] if found else ""
    title = record.get("title", "").strip()
    if not title:
        raise ValueError("Missing listing title")
    price = money(record.get("price_text", ""))
    original = money(record.get("original_price_text", ""))
    attributes = explicit_fields(record)
    p = Product("Best Buy", title, role="retailer", url=url, sku=str(sku), currency="USD",
        brand=attributes["brand"] or (title.split(" - ", 1)[0] if " - " in title else ""),
        model=attributes["model"], gtin=attributes["gtin"], specs=attributes["specs"],
        condition="unknown", price=price, original_price=original,
        availability=record.get("availability", "unknown"), merchant="Best Buy", target_country=market,
        moq=1, collection_method="bestbuy_browser", image_url=record.get("image_url", ""),
        image_reuse_permitted=False, source_attributes={"on_sale": bool(price is not None and original is not None and original > price),
            "clearance": record.get("clearance", False), "reference_price_status": "Advertised; not independently verified",
            "delivery_to_target": "Unverified; confirm delivery and import/forwarding costs"})
    p.states = {"title": "verified", "price": "verified" if price is not None else "unavailable",
                "original_price": "verified" if original is not None else "unavailable", "url": "verified",
                "availability": "verified" if p.availability != "unknown" else "unavailable", "moq": "estimated",
                "target_country": "estimated"}
    p.states["brand"] = "verified" if attributes["brand"] else "estimated"
    p.states["model"] = "verified" if p.model else "unavailable"
    p.states["gtin"] = "verified" if p.gtin else "unavailable"
    p.states["specs"] = "verified" if p.specs else "unavailable"
    return p


def card_records(page, limit):
    cards = page.locator("li.sku-item, .product-list-item, [data-testid='product-card']")
    records = []
    # Sponsored cards can remain price skeletons while ordinary cards have quotes.
    # Inspect a bounded set already present in the DOM, then prefer usable prices.
    for index in range(min(cards.count(), limit * 3, 100)):
        card = cards.nth(index)
        links = card.locator(".sku-title a, a[data-testid='product-title'], h2 a, h3 a, a.product-list-item-link")
        if not links.count():
            continue
        link = links.first
        price = card.locator("[data-testid='price-block-customer-price'] .sr-only, .priceView-customer-price, [data-testid='customer-price'], .price-block .customer-price")
        original = card.locator("[data-testid='price-block-regular-price'], .priceView-previous-price, [data-testid='regular-price']")
        text = card.inner_text(timeout=1500)
        attributes = catalog_labels(text)
        buttons = card.get_by_role("button", name=re.compile(r"^Add to Cart$", re.I))
        available = "unknown"
        if buttons.count() and buttons.first.is_enabled():
            available = "in_stock"
        elif re.search(r"sold out|not available|unavailable", text, re.I):
            available = "out_of_stock"
        image = card.locator("img")
        image_url = image.first.get_attribute("src") if image.count() else ""
        if image_url and not image_url.startswith("https://"):
            image_url = ""
        records.append({"title": link.inner_text(timeout=1500), "url": link.get_attribute("href"), **attributes,
            "sku": card.get_attribute("data-sku-id") or "", "availability": available,
            "price_text": price.first.inner_text(timeout=1500) if price.count() else "",
            "original_price_text": original.first.inner_text(timeout=1500) if original.count() else "",
            "image_url": image_url or "", "clearance": "clearance" in text.lower()})
    records.sort(key=lambda row: money(row.get("price_text", "")) is None)
    return records[:limit]


class BestBuyBrowserConnector:
    def __init__(self, request_observer=None):
        self._request_observer = request_observer

    def discover(self, query):
        from playwright.sync_api import sync_playwright

        if not LOCK.acquire(blocking=False):
            raise SourceError("browser_busy", "A browser collection is already running. Wait for it to finish.")
        configure_browser_path()
        try:
            host, address = validate_url(f"https://{HOST}/", HOST)
            with sync_playwright() as playwright:
                try:
                    browser = playwright.chromium.launch(headless=True, chromium_sandbox=True, env=browser_env(),
                        args=[f"--host-resolver-rules=MAP {host} {address},MAP * ~NOTFOUND", "--no-proxy-server",
                              "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
                except Exception:
                    raise SourceError("browser_missing", "Chromium could not start. See Help → Browser setup; the application needs Playwright's official browser installed.") from None
                try:
                    context = browser.new_context(java_script_enabled=True, accept_downloads=False,
                        service_workers="block", extra_http_headers={"X-Digital-Agent": "ProductOpportunityFinder"})
                    # Ordinary website scripts run only inside sandboxed Chromium.
                    # Only same-origin read requests are allowed; no account/session
                    # automation, form submissions, third parties or persisted profiles.
                    requests = 0

                    def route_request(route):
                        nonlocal requests
                        if self._request_observer:
                            self._request_observer(route.request)
                        if read_request_allowed(route.request.method, route.request.url, route.request.resource_type, requests, route.request.post_data):
                            requests += 1
                            route.continue_()
                        else:
                            route.abort()

                    context.route("**/*", route_request)
                    context.route_web_socket("**/*", lambda socket: socket.close())
                    page = context.new_page()
                    products, seen = [], set()
                    started = time.monotonic()
                    for number in range(1, query.max_pages + 1):
                        if number > 1 and not any((query.keywords, query.brand, query.model, query.category_id, query.category_name)):
                            break
                        if time.monotonic() - started > 45:
                            break
                        try:
                            response = page.goto(listing_url(query, number), wait_until="commit", timeout=20000)
                            page.wait_for_load_state("domcontentloaded", timeout=30000)
                            if page.locator("a.us-link").count():
                                # Use the site's own country selector. Do not fabricate
                                # cookies or evade location/account access controls.
                                with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                                    page.locator("a.us-link").first.click(timeout=8000)
                                response = page.goto(listing_url(query, number), wait_until="commit", timeout=20000)
                                page.wait_for_load_state("domcontentloaded", timeout=30000)
                        except Exception:
                            raise SourceError("browser_network", "Best Buy's public page did not load within the time limit. No products were substituted. Try later or check your network.") from None
                        if response is None:
                            raise SourceError("browser_network", "Best Buy did not return a public page.")
                        if response.status in (401, 403, 429):
                            raise from_http(response.status)
                        if response.status >= 400:
                            raise SourceError("page_unavailable", "Best Buy returned an unavailable public page. Try again later.")
                        mime = response.headers.get("content-type", "").split(";")[0].lower().strip()
                        if mime not in {"text/html", "application/xhtml+xml"}:
                            raise SourceError("content_type", "Best Buy returned an unexpected content type. Collection stopped.")
                        if int(response.headers.get("content-length", "0")) > MAX_RESPONSE:
                            raise SourceError("page_size", "The product page exceeds the allowed response size.")
                        content = page.content()
                        if len(content.encode()) > MAX_RESPONSE:
                            raise SourceError("page_size", "The public page exceeded the document size limit.")
                        visible_text = page.locator("body").inner_text(timeout=3000).lower()
                        if any(term in visible_text for term in ("captcha", "verify you are human", "access denied", "robot or human")):
                            raise SourceError("access_barrier", "Best Buy returned an access challenge. Collection stopped; no bypass was attempted.")
                        try:
                            page.locator("li.sku-item, .product-list-item, [data-testid='product-card']").first.wait_for(timeout=8000)
                        except Exception:
                            pass
                        try:
                            page.locator("[data-testid='price-block-customer-price'] .sr-only, .priceView-customer-price, [data-testid='customer-price'], .price-block .customer-price, .priceView-hero-price").first.wait_for(state="attached", timeout=12000)
                        except Exception:
                            pass
                        records = card_records(page, query.limit)
                        if not records and not products:
                            raise SourceError("page_unreadable", "Best Buy returned no readable product cards. The page may require scripts, authentication or a changed layout. No sample data was substituted.")
                        for record in records:
                            product = normalize_card(record, query.target_market)
                            if product.url not in seen:
                                products.append(product)
                                seen.add(product.url)
                            if len(products) >= query.limit:
                                return products
                        if not records:
                            break
                        time.sleep(2)
                    return products
                finally:
                    browser.close()
        finally:
            LOCK.release()
