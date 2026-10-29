import json

import pytest

from pof.listing_refresh import refresh_listing
from pof.models import Product
from pof.review_store import ReviewStore
from pof.storage import Store


class Page:
    def __init__(self, sku="123"):
        self.sku = sku

    def fetch(self, url, host, types):
        assert host == "www.bestbuy.com"
        return ('<script type="application/ld+json">' + json.dumps({"@type": "Product", "name": "Fixture bottle", "sku": self.sku,
            "offers": {"@type": "Offer", "price": 12.34, "priceCurrency": "USD"}}) + '</script>').encode()


def test_exact_listing_refresh_appends_price_without_losing_rating(tmp_path):
    store = Store(tmp_path / "research.sqlite3")
    p = Product("Best Buy", "Fixture bottle", sku="123", url="https://www.bestbuy.com/product/bottle/sku/123", shipping=2, moq=1)
    store.add_run("Original", [p])
    review = ReviewStore(store)
    cid = review.items()[0]["id"]
    review.rate(cid, "Like", "Keep my notes")
    refresh_listing(p, store, Page())
    item = review.items()[0]
    assert item["id"] == cid
    assert item["product"].price == 12.34
    assert item["rating"] == "Like" and item["note"] == "Keep my notes"
    assert item["product"].state("shipping") == "stale"
    assert len(review.history(cid)) == 2


def test_unmatched_or_untrusted_listing_does_not_replace_price(tmp_path):
    store = Store(tmp_path / "research.sqlite3")
    p = Product("Best Buy", "Bottle", sku="123", url="https://www.bestbuy.com/product/bottle/sku/123")
    with pytest.raises(ValueError):
        refresh_listing(p, store, Page("different"))
    assert not store.products()
    p.url = "https://unrelated.example/product"
    with pytest.raises(ValueError):
        refresh_listing(p, store, Page())
