"""Public-browser parser contracts; actual site verification is recorded separately."""
import pytest

from pof.live.bestbuy_browser import (listing_url, money, normalize_card, read_request_allowed,
                                     browser_installed, configure_browser_path, card_records)
from pof.live.query import ResearchQuery


def test_browser_requires_no_api_key_and_supports_broad_discovery():
    assert "apiKey" not in listing_url(ResearchQuery(keywords="usb hub"))
    assert "top-deals" in listing_url(ResearchQuery())
    assert "usb+hub" in listing_url(ResearchQuery(keywords="usb hub"))


def test_visible_price_not_financing_or_range():
    assert money("$1,234.56") == 1234.56
    assert money("$10.00 /mo") is None
    assert money("From $10.00") is None
    assert money("$10.00 - $20.00") is None


def test_browser_card_keeps_unknown_costs_and_original_evidence():
    p = normalize_card({"title": "Test Brand - Fixture", "url": "/site/item/1234567.p?skuId=1234567",
        "price_text": "$29.99", "original_price_text": "$39.99"})
    assert p.price == 29.99
    assert p.sku == "1234567"
    assert p.shipping is None
    assert p.availability == "unknown"
    assert p.collection_method == "bestbuy_browser"
    assert p.state("price") == "verified"
    assert p.source_attributes["on_sale"]
    assert not p.demo
    with pytest.raises(ValueError):
        normalize_card({"title": "Bad", "url": "https://evil.com/item"})


def test_native_browser_network_scope_and_no_actions():
    assert read_request_allowed("GET", "https://www.bestbuy.com/site/searchpage.jsp", "document", 0)
    for url in ("http://127.0.0.1", "https://www.bestbuy.com:8443/site/", "https://evil.com/", "https://www.bestbuy.com/checkout"):
        assert not read_request_allowed("GET", url, "document", 0)
    assert not read_request_allowed("POST", "https://www.bestbuy.com/api/purchase", "fetch", 0)
    assert not read_request_allowed("GET", "https://www.bestbuy.com/site/", "document", 120)
    assert read_request_allowed("POST", "https://www.bestbuy.com/gateway/graphql", "fetch", 0, '{"query":"query Catalog { products { name } }"}')
    assert not read_request_allowed("POST", "https://www.bestbuy.com/gateway/graphql", "fetch", 0, '{"query":"mutation Buy { checkout }"}')


@pytest.mark.skipif(not browser_installed(), reason="Optional project Chromium is not installed")
def test_current_price_widget_with_real_chromium():
    from playwright.sync_api import sync_playwright
    configure_browser_path()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            page = browser.new_page()
            page.route("**/*", lambda route: route.abort())
            page.set_content('''<div class="product-list-item">
                <a class="product-list-item-link" href="https://www.bestbuy.com/product/sponsor/sku/9999999">Sponsored skeleton</a>
                <div class="skeleton-product-price"></div></div><div class="product-list-item">
                <a class="product-list-item-link" href="https://www.bestbuy.com/product/test/sku/1234567"><h3>Test Brand - Contract fixture</h3></a>
                <div data-testid="price-block-customer-price"><span class="sr-only">$22.49</span><span aria-hidden="true">$22.49</span></div>
                <div data-testid="price-block-regular-price">$24.99</div><button>Add to cart</button></div>''')
            rows = card_records(page, 1)
            assert len(rows) == 1
            product = normalize_card(rows[0])
            assert product.price == 22.49
            assert product.original_price == 24.99
            assert product.availability == "in_stock"
        finally:
            browser.close()
