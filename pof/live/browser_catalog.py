"""Key-free bounded catalog extraction for explicitly permitted public websites.

Uses real Playwright static-document parsing. Does not bypass login, CAPTCHA, robots,
or fetch undocumented internal APIs. Browser binaries must be explicitly installed.
"""
from html.parser import HTMLParser
import time
import re
from urllib.parse import quote, urljoin, urlsplit

import httpx

from pof.browser import extract_page
from pof.extraction import parse_products
from pof.live.errors import SourceError
from pof.live.robots import allowed
from pof.security import SafeHTTP, validate_url


class CatalogLinks(HTMLParser):
    def __init__(self, origin, prefix):
        super().__init__()
        self.origin, self.prefix = origin, prefix
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        try:
            absolute = str(httpx.URL(urljoin(self.origin, href)))
        except ValueError:
            return
        parsed = urlsplit(absolute)
        if re.search(r"%(?:2e|2f|5c|0[0-9a-f]|1[0-9a-f])", parsed.path, re.I):
            return
        if (parsed.scheme == "https" and parsed.hostname == urlsplit(self.origin).hostname
                and parsed.path.startswith(self.prefix) and not parsed.fragment
                and not parsed.username and not parsed.password and absolute not in self.links):
            self.links.append(absolute)


def discover_browser(source: dict, query, http=None, render=None):
    if not source.get("permission_confirmed") or not source.get("permission_reference", "").strip():
        raise SourceError("permission_required", "Record the website's automation permission or written authorization in Source Manager first.")
    template = source.get("search_url_template", "")
    host = source.get("allowed_host", "")
    prefix = source.get("product_path_prefix", "/product/")
    if not prefix.startswith("/") or prefix == "/" or len(prefix) > 200:
        raise SourceError("configuration", "Set a specific product-link path prefix in Source Manager.")
    http = http or SafeHTTP(interval=max(1, float(source.get("interval", 2))))
    render = render or extract_page
    robots = http.fetch(f"https://{host}/robots.txt", host, ("text/plain", "text/html")).decode("utf-8", errors="replace")
    started = time.monotonic()
    products, visited = [], set()
    page_count = query.max_pages if "{page}" in template else 1
    for page in range(1, page_count + 1):
        url = template.replace("{keywords}", quote(query.keywords, safe="")).replace("{category}", quote(query.category_name, safe="")).replace("{page}", str(page))
        if "{" in url or "}" in url:
            raise SourceError("configuration", "Only {keywords}, {category} and {page} are supported in catalog URLs.")
        if re.search(r"%(?:2e|2f|5c)", urlsplit(url).path, re.I):
            raise SourceError("configuration", "Catalog paths must not contain encoded traversal or separators.")
        url = str(httpx.URL(url))
        validate_url(url, host)
        if not allowed(robots, url):
            raise SourceError("robots_restricted", "The site's robots rules do not permit this catalog URL. Collection stopped.")
        if time.monotonic() - started > 45:
            raise SourceError("time_limit", "The browser collection reached its time limit. Narrow the search or lower the product limit.")
        raw = render(url, host, http)
        if any(term in raw.lower() for term in (b"captcha", b"verify you are human", b"access denied")):
            raise SourceError("access_barrier", "The website presented an access barrier. Collection stopped without bypassing it.")
        parser = CatalogLinks(url, prefix)
        parser.feed(raw.decode("utf-8", errors="replace"))
        for link in parser.links[:query.limit]:
            if link in visited or not allowed(robots, link):
                continue
            visited.add(link)
            if time.monotonic() - started > 45:
                break
            page_raw = render(link, host, http)
            if any(term in page_raw.lower() for term in (b"captcha", b"access denied", b"verify you are human")):
                raise SourceError("access_barrier", "A product page presented an access barrier. Collection stopped.")
            try:
                found = parse_products(page_raw, {**source, "url": link})
            except ValueError:
                continue
            for product in found:
                product.collection_method = "permitted_browser"
                product.target_country = query.target_market
                products.append(product)
                if len(products) >= query.limit:
                    return products
    if not products:
        raise SourceError("no_structured_products", "No supported public product records were found. This adapter needs permitted catalog links and Product structured data; it cannot unlock protected or script-only listings.")
    return products
