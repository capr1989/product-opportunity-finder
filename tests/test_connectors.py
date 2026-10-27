from dataclasses import asdict, replace
import json

import pytest

from pof.connectors import FeedConnector, PublicPageConnector, status
from pof.demo import demo_products
from pof.demand import diagnostics, import_keywords
from pof.extraction import parse_products
from pof.finance import Assumptions
from pof.research import deals, opportunities
from pof.scoring import DEFAULT_WEIGHTS, score


class FakeHTTP:
    def __init__(self, body):
        self.body = body

    def fetch(self, *args):
        return self.body


SOURCE = {"name": "test", "role": "supplier", "url": "https://example.com/product", "allowed_host": "example.com"}


def test_feed_and_import_status():
    source = {**SOURCE, "kind": "json"}
    result = FeedConnector().collect(source, FakeHTTP(b'[{"source":"x","title":"Widget","price":10}]'))
    assert result[0].source == "test"
    assert not result[0].demo
    assert status({"enabled": True, "kind": "import"}).startswith("import-only")
    with pytest.raises(ValueError):
        FeedConnector().collect(source, FakeHTTP(b'{"not":"list"}'))


def test_structured_data_and_barrier():
    data = {"@type": "Product", "name": "Widget", "brand": {"name": "Example"},
            "offers": {"price": "12.50", "priceCurrency": "USD"}}
    raw = ('<script type="application/ld+json">' + json.dumps(data) + '</script>').encode()
    product = parse_products(raw, SOURCE)[0]
    assert product.price == 12.5
    assert product.shipping is None
    assert product.state("price") == "verified"
    with pytest.raises(ValueError):
        PublicPageConnector().collect({**SOURCE, "kind": "public_page"}, FakeHTTP(b"CAPTCHA"))


def test_profit_matching_and_deals():
    products = demo_products()
    rows = opportunities(products, Assumptions(), dropship=True)
    assert len(rows) == 8
    assert all(r["known"] for r in rows)
    assert deals(products)
    # Advertised original price alone cannot create a deal.
    assert not deals([replace(products[1], original_price=999)])
    pair = rows[0]["pair"]
    assert len(opportunities(products, Assumptions(), reviews={pair: {"decision": "reject"}}, dropship=True)) == 7


def test_demand_and_scoring_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
    assert not diagnostics()["credentials_present"]
    rows = import_keywords(b"keyword,monthly_searches,cpc\nwidget,100,0.25")
    assert rows[0]["status"] == "estimated"
    p = replace(demo_products()[0], monthly_searches=None)
    value, breakdown = score(p, {"known": False}, 0, DEFAULT_WEIGHTS)
    assert breakdown["demand"]["points"] == 0
    assert 0 <= value <= 100
    assert asdict(Assumptions())["advertising"] == 5
