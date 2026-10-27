"""Contract tests for permitted key-free catalog discovery; not live retailer verification."""
import json
import socket

import pytest

from pof.live.browser_catalog import CatalogLinks, discover_browser
from pof.live.query import ResearchQuery


SOURCE = {"name": "Authorized test source", "role": "retailer", "allowed_host": "example.com",
          "search_url_template": "https://example.com/catalog?q={keywords}&page={page}",
          "product_path_prefix": "/product/", "permission_reference": "Test fixture permission only", "permission_confirmed": True}


class RobotsHTTP:
    def __init__(self, disallow=""):
        self.disallow = disallow

    def fetch(self, *args):
        return f"User-agent: *\nDisallow: {self.disallow}\n".encode()


def test_catalog_links_never_follow_external_or_unrelated_paths():
    parser = CatalogLinks("https://example.com/catalog", "/product/")
    parser.feed('<a href="https://evil.com/product/1">bad</a><a href="/account">bad</a><a href="/product/1">good</a>')
    parser.feed('<a href="/product/../private/1">bad</a><a href="/product/%2e%2e/private">bad</a>')
    assert parser.links == ["https://example.com/product/1"]


def test_permission_required_before_any_request():
    with pytest.raises(ValueError, match="permission"):
        discover_browser({**SOURCE, "permission_reference": ""}, ResearchQuery())


def test_browser_catalog_respects_robots_and_parses_bounded_products(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))])
    calls = []

    def render(url, host, http):
        calls.append(url)
        if "/catalog" in url:
            return b'<a href="/product/1">one</a><a href="/product/2">two</a>'
        data = {"@type": "Product", "name": "Test contract product", "offers": {"price": 12, "priceCurrency": "USD", "availability": "https://schema.org/InStock"}}
        return ('<script type="application/ld+json">' + json.dumps(data) + '</script>').encode()

    products = discover_browser(SOURCE, ResearchQuery(limit=1), RobotsHTTP(), render)
    assert len(products) == 1
    assert len(calls) == 2
    assert products[0].availability == "in_stock"
    assert products[0].collection_method == "permitted_browser"
    assert not products[0].demo
    with pytest.raises(ValueError, match="robots"):
        discover_browser(SOURCE, ResearchQuery(limit=1), RobotsHTTP("/"), render)


def test_captcha_stops_catalog(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))])
    with pytest.raises(ValueError, match="barrier"):
        discover_browser(SOURCE, ResearchQuery(), RobotsHTTP(), lambda *args: b"verify you are human CAPTCHA")


def test_robots_wildcards_and_specific_agents():
    from pof.live.robots import allowed
    rules = "User-agent: *\nDisallow: /private/*\nDisallow: /*?secret=*\nAllow: /private/public$\n"
    assert not allowed(rules, "https://example.com/private/account")
    assert not allowed(rules, "https://example.com/catalog?secret=test")
    assert allowed(rules, "https://example.com/private/public")
    assert not allowed(rules, "https://example.com/private/public/other")
    assert not allowed("<html>missing robots document</html>", "https://example.com/")
