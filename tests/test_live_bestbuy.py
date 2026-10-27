"""Contract tests written before implementing the Best Buy discovery adapter."""
import json
import socket

import httpx
import pytest

from pof.live.bestbuy import BestBuyConnector
from pof.live.query import ResearchQuery
from pof.security import SafeHTTP


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))])


def response_record():
    return {"sku": 1234567, "name": "Contract fixture headphones", "salePrice": 40,
        "regularPrice": 60, "manufacturer": "Test Brand", "modelNumber": "TEST-1",
        "upc": "0012345678905", "onlineAvailability": True, "shippingCost": 3.99,
        "url": "https://www.bestbuy.com/site/test/1234567.p?skuId=1234567",
        "image": "https://pisces.bbystatic.com/image2/test.jpg", "onSale": True,
        "categoryPath": [{"id": "a", "name": "Audio"}, {"id": "b", "name": "Headphones"}]}


def test_keyword_free_catalog_discovery_normalizes_actual_api_shape(public_dns):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "api.bestbuy.com"
        assert request.url.params["apiKey"] == "private-test-value"
        assert "active=true" in request.url.path
        assert "search=" not in request.url.path
        return httpx.Response(200, json={"products": [response_record()], "totalPages": 1,
            "canonicalUrl": "THIS MUST NEVER BE PERSISTED private-test-value"})
    connector = BestBuyConnector("private-test-value", SafeHTTP(0.5, httpx.MockTransport(handler)))
    products = connector.discover(ResearchQuery(limit=5))
    assert len(seen) == 1
    assert products[0].price == 40
    assert products[0].brand == "Test Brand"
    assert products[0].category == "Audio"
    assert products[0].subcategory == "Headphones"
    assert products[0].availability == "in_stock"
    assert products[0].shipping == 3.99
    assert products[0].state("price") == "verified"
    assert not products[0].demo
    assert "private-test-value" not in json.dumps(products[0].record())


def test_query_is_typed_not_raw_bestbuy_expression():
    query = ResearchQuery(keywords="usb hub", brand="Test Brand", category_id="abcat0500000",
                          minimum_price=10, maximum_price=50, on_sale=True, limit=5)
    expression = BestBuyConnector.expression(query)
    assert "salePrice>=10" in expression and "salePrice<=50" in expression
    assert "onSale=true" in expression
    with pytest.raises(ValueError):
        BestBuyConnector.expression(ResearchQuery(brand='Apple)&apiKey=stolen'))


def test_credentials_required_without_substituting_fixtures():
    with pytest.raises(ValueError, match="key"):
        BestBuyConnector("")


def test_unknown_shipping_is_not_free(public_dns):
    record = response_record()
    record.pop("shippingCost")
    record.pop("onlineAvailability")
    def handler(request):
        return httpx.Response(200, json={"products": [record], "totalPages": 1})
    products = BestBuyConnector("test-key", SafeHTTP(0.5, httpx.MockTransport(handler))).discover(ResearchQuery(limit=1))
    assert products[0].shipping is None
    assert products[0].availability == "unknown"


def test_api_key_is_not_in_errors_or_logs(public_dns, caplog):
    caplog.set_level("DEBUG")
    def handler(request):
        return httpx.Response(403, text="key=private-test-value")
    connector = BestBuyConnector("private-test-value", SafeHTTP(0.5, httpx.MockTransport(handler)))
    with pytest.raises(ValueError) as error:
        connector.discover(ResearchQuery(limit=1))
    assert "private-test-value" not in str(error.value) + caplog.text


def test_signed_product_links_do_not_change_catalog_identity():
    from dataclasses import replace
    from pof.storage import Store
    a = BestBuyConnector.normalize(response_record(), "US")
    b = replace(a, url="https://api.bestbuy.com/click/changed/1234567/pdp")
    assert Store.identity(a) == Store.identity(b)


def test_bounded_pagination_and_empty_results(public_dns):
    calls = []
    def handler(request):
        calls.append(request.url.params["page"])
        return httpx.Response(200, json={"products": [response_record()], "totalPages": 10000})
    connector = BestBuyConnector("test-key", SafeHTTP(0.5, httpx.MockTransport(handler)))
    connector.discover(ResearchQuery(limit=100, max_pages=2))
    assert len(calls) == 2


def test_expired_bestbuy_content_is_purged_from_history_and_cache(tmp_path):
    from datetime import UTC, datetime, timedelta
    from pof.models import Product
    from pof.storage import Store
    store = Store(tmp_path / "research.sqlite3")
    old = (datetime.now(UTC) - timedelta(hours=73)).isoformat()
    product = Product("Best Buy", "Expired API content", collected_at=old,
                      collection_method="bestbuy_api", retention_hours=72)
    store.add_run("old", [product])
    store.purge_expired()
    assert store.products() == []
    assert store.history()[0][3] == 0
