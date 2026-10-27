"""Key-free public server-rendered catalogs parsed in isolated Playwright DOMs."""
from contextlib import contextmanager
import json
import re
from urllib.parse import quote, urlencode

from pof.browser import LOCK, browser_env
from pof.live.bestbuy_browser import configure_browser_path, money
from pof.live.errors import SourceError
from pof.models import Product
from pof.security import MAX_RESPONSE, SafeHTTP


@contextmanager
def static_dom(raw):
    from playwright.sync_api import sync_playwright
    if len(raw) > MAX_RESPONSE:
        raise SourceError("page_size", "The public catalog exceeded the document size limit.")
    if not LOCK.acquire(blocking=False):
        raise SourceError("browser_busy", "Another browser collection is running. Please wait.")
    configure_browser_path()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, chromium_sandbox=True, env=browser_env())
            try:
                context = browser.new_context(java_script_enabled=False, accept_downloads=False, service_workers="block")
                context.route("**/*", lambda route: route.abort())
                page = context.new_page()
                page.set_content(raw.decode("utf-8", errors="replace"), timeout=10000, wait_until="domcontentloaded")
                visible = page.locator("body").inner_text(timeout=3000).lower()
                if any(term in visible for term in ("verify you are human", "robot check", "enter the characters you see below", "access denied")):
                    raise SourceError("access_barrier", "The source returned an access challenge. Collection stopped without bypassing it.")
                yield page
            finally:
                browser.close()
    finally:
        LOCK.release()


def amazon_url(query, page):
    categories = {"abcat0500000": "computers", "abcat0204000": "electronics", "abcat0101000": "electronics",
                  "abcat0800000": "mobile", "abcat0900000": "appliances"}
    terms = " ".join(v for v in (query.keywords, query.category_name, query.brand, query.model) if v)
    if not terms:
        terms = {"abcat0500000": "computer accessories", "abcat0204000": "headphones",
                 "abcat0101000": "televisions", "abcat0800000": "cell phones",
                 "abcat0900000": "home appliances"}.get(query.category_id, "electronics accessories")
    return "https://www.amazon.com/s?" + urlencode({"k": terms, "i": categories.get(query.category_id, "electronics"), "page": page})


class AmazonPublicConnector:
    def __init__(self, http=None):
        self.http = http or SafeHTTP(2)

    def discover(self, query):
        products, seen = [], set()
        for number in range(1, query.max_pages + 1):
            raw = self.http.fetch(amazon_url(query, number), "www.amazon.com", ("text/html", "application/xhtml+xml"))
            with static_dom(raw) as page:
                cards = page.locator(".s-main-slot [data-component-type='s-search-result'][data-asin]")
                card_count = cards.count()
                for index in range(min(card_count, 100)):
                    card = cards.nth(index)
                    asin = card.get_attribute("data-asin") or ""
                    heading = card.locator("h2")
                    if not re.fullmatch(r"[A-Z0-9]{10}", asin) or asin in seen or not heading.count():
                        continue
                    title = heading.first.inner_text(timeout=2000).strip()
                    if not title:
                        continue
                    price = card.locator(".a-price:not(.a-text-price) .a-offscreen")
                    listed_price = money(price.first.text_content() or "") if price.count() else None
                    old = card.locator(".a-price.a-text-price .a-offscreen")
                    original = money(old.first.text_content() or "") if old.count() else None
                    image = card.locator("img.s-image")
                    image_url = image.first.get_attribute("src") if image.count() else ""
                    if not image_url or not image_url.startswith("https://"):
                        image_url = ""
                    p = Product("Amazon US", title, role="retailer", sku=asin, url=f"https://www.amazon.com/dp/{asin}",
                        price=listed_price, original_price=original, currency="USD", condition="unknown", moq=1,
                        target_country=query.target_market, image_url=image_url, image_reuse_permitted=False,
                        collection_method="amazon_public", source_attributes={"asin": asin,
                            "on_sale": bool(listed_price is not None and original is not None and original > listed_price),
                            "price_basis": "advertised_offer", "seller_and_variant": "unconfirmed",
                            "delivery_to_target": "unverified", "broad_default": "Electronics catalog"})
                    p.states = {"title": "verified", "sku": "verified", "price": "verified" if listed_price is not None else "unavailable",
                        "original_price": "verified" if original is not None else "unavailable", "url": "verified", "moq": "estimated"}
                    products.append(p)
                    seen.add(asin)
                    if len(products) >= query.limit:
                        return products
            if not card_count:
                break
        if not products:
            raise SourceError("page_unreadable", "Amazon returned no readable public product listings. It may require a different search, location choice or authorized access.")
        return products


def aliexpress_records(script, market, limit):
    match = re.search(r"window\._dida_config_\._init_data_\s*=\s*\{\s*data:\s*", script)
    if not match:
        return []
    try:
        # Decode the JSON data object only; never evaluate the surrounding JavaScript.
        data, _ = json.JSONDecoder().raw_decode(script[match.end():])
    except (ValueError, RecursionError):
        raise SourceError("invalid_product_data", "AliExpress returned a catalog format that could not be safely read.") from None
    pending, products, seen = [data], [], set()
    visited = 0
    while pending and visited < 20000 and len(products) < limit:
        value = pending.pop()
        visited += 1
        if isinstance(value, list):
            pending.extend(reversed(value))
        elif isinstance(value, dict):
            if not value.get("productId"):
                pending.extend(reversed(list(value.values())))
                continue
            identifier = str(value["productId"])
            if not identifier.isdigit() or identifier in seen:
                continue
            title = (value.get("title") or {}).get("displayTitle", "")
            price = (value.get("prices") or {}).get("salePrice") or {}
            if not title:
                continue
            image = (value.get("image") or {}).get("imgUrl", "")
            if image.startswith("//"):
                image = "https:" + image
            if image and not image.startswith("https://"):
                image = ""
            p = Product("AliExpress", title, role="supplier", sku=identifier,
                url=f"https://www.aliexpress.com/item/{identifier}.html", price=price.get("minPrice"),
                currency=price.get("currencyCode") or "UNKNOWN", condition="unknown", target_country=market,
                image_url=image, image_reuse_permitted=False, collection_method="aliexpress_public",
                rating=(value.get("evaluation") or {}).get("starRating"),
                source_attributes={"price_basis": "advertised_minimum", "price_display": price.get("formattedPrice", ""),
                    "on_sale": bool(price.get("discount", 0) > 0),
                    "price_conditions": (value.get("prices") or {}).get("builderType", "unconfirmed"),
                    "variant_confirmation_required": True, "delivery_to_target": "unverified"})
            p.states = {"title": "verified", "sku": "verified", "price": "verified" if p.price is not None else "unavailable",
                        "currency": "verified" if p.currency != "UNKNOWN" else "unavailable", "url": "verified"}
            products.append(p)
            seen.add(identifier)
    return products


class AliExpressPublicConnector:
    def __init__(self, http=None):
        self.http = http or SafeHTTP(2)

    def discover(self, query):
        hints = {"abcat0500000": "computer accessories", "abcat0204000": "headphones", "abcat0101000": "tv accessories",
                 "abcat0800000": "phone accessories", "abcat0900000": "home appliances"}
        terms = " ".join(v for v in (query.keywords, query.category_name, query.brand, query.model) if v) or hints.get(query.category_id, "electronics accessories")
        url = "https://www.aliexpress.com/w/wholesale-" + quote(terms.replace(" ", "-"), safe="-") + ".html"
        raw = self.http.fetch(url, "www.aliexpress.com", ("text/html", "application/xhtml+xml"))
        with static_dom(raw) as page:
            for script in page.locator("script").all_text_contents():
                if "window._dida_config_._init_data_" in script and "productId" in script:
                    products = aliexpress_records(script, query.target_market, query.limit)
                    if products:
                        return products
        raise SourceError("page_unreadable", "AliExpress returned no safely readable public product records. No demo data was substituted.")
