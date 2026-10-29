from dataclasses import replace

from pof.models import Product
from pof.review_store import ReviewStore
from pof.storage import Store


def test_ratings_notes_favorites_persist_and_do_not_duplicate(tmp_path):
    path = tmp_path / "research.sqlite3"
    store = Store(path)
    p = Product("Test", "USB hub", url="https://example.com/item", price=5)
    first = store.add_run("Quick", [p])
    review = ReviewStore(store)
    cid = review.items()[0]["id"]
    review.rate(cid, "Love it", "Check shipping")
    second = store.add_run("Deep", [replace(p, price=8)])
    review = ReviewStore(Store(path))
    assert len(review.items()) == 1
    assert review.items()[0]["note"] == "Check shipping"
    assert len(review.items(favorites=True)) == 1
    assert review.items([first])[0]["product"].price == 5
    assert review.items([second])[0]["product"].price == 8
    assert len(review.history(cid)) == 2
    review.rate(cid, "Maybe later")
    assert not review.items(favorites=True)
    assert review.items(watchlist=True)
    review.rate(cid, "Pass")
    assert len(review.items()) == 1
    assert review.items()[0]["note"] == "Check shipping"


def test_variants_remain_distinct_and_migration_is_backed_up(tmp_path):
    store = Store(tmp_path / "research.sqlite3")
    p = Product("Test", "Bottle", url="https://example.com/bottle", specs={"size": "small"})
    store.add_run("Variants", [p, replace(p, specs={"size": "large"})])
    assert len(ReviewStore(store).items()) == 2
    assert len(list(tmp_path.glob("*.pre-review-v3.*.sqlite3"))) == 1
    Store(store.path)
    assert len(list(tmp_path.glob("*.pre-review-v3.*.sqlite3"))) == 1


