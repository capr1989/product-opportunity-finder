from dataclasses import replace

from pof.models import Product
from pof.review_store import ReviewStore
from pof.storage import Store
import json
import sqlite3
import pytest


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


def legacy_database(path):
    p = Product("Legacy", "Existing item", url="https://example.com/legacy", price=12)
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE migrations(version INTEGER PRIMARY KEY,applied TEXT);"
            "INSERT INTO migrations VALUES(1,'legacy');"
            "CREATE TABLE runs(id INTEGER PRIMARY KEY,name TEXT,created TEXT);"
            "INSERT INTO runs VALUES(1,'Existing scan','legacy');"
            "CREATE TABLE snapshots(id INTEGER PRIMARY KEY,run_id INTEGER,identity TEXT,payload TEXT,created TEXT);")
        db.execute("INSERT INTO snapshots VALUES(1,1,?,?,?)", (Store.identity(p), json.dumps(p.record()), p.collected_at))
    return p


def test_legacy_migration_preserves_payload_and_backup(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    original = legacy_database(path)
    store = Store(path)
    assert store.products()[0].record() == original.record()
    assert ReviewStore(store).items()[0]["product"].record() == original.record()
    with sqlite3.connect(next(tmp_path.glob("*.pre-review-v3.*.sqlite3"))) as backup:
        assert json.loads(backup.execute("SELECT payload FROM snapshots").fetchone()[0]) == original.record()


def test_failed_migration_rolls_back_and_keeps_original(tmp_path, monkeypatch):
    import pof.review_store as module
    path = tmp_path / "legacy.sqlite3"
    original = legacy_database(path)
    def fail(*args):
        raise RuntimeError("simulated migration failure")
    monkeypatch.setattr(module, "associate", fail)
    with pytest.raises(RuntimeError):
        Store(path)
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT 1 FROM migrations WHERE version=3").fetchone()
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='candidates'").fetchone()
        assert json.loads(db.execute("SELECT payload FROM snapshots").fetchone()[0]) == original.record()


def test_stable_source_sku_retains_rating_across_listing_urls(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    p = Product("Merchant", "Item", sku="same-source-sku", url="https://example.com/old")
    store.add_run("First", [p])
    cid = ReviewStore(store).items()[0]["id"]
    ReviewStore(store).rate(cid, "Like")
    store.add_run("Second", [replace(p, url="https://example.com/new")])
    assert len(ReviewStore(store).items()) == 1
    assert ReviewStore(store).items()[0]["rating"] == "Like"
    assert len(ReviewStore(store).history(cid)) == 2
    Store(store.path)
    assert len(list(tmp_path.glob("*.pre-review-v3.*.sqlite3"))) == 1


def test_downloaded_backup_restores_without_wal_companion(tmp_path):
    store = Store(tmp_path / "research.sqlite3")
    store.add_run("Source", [Product("Source", "Original", price=7)])
    cid = ReviewStore(store).items()[0]["id"]
    ReviewStore(store).rate(cid, "Love it", "Preserve me")
    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(store.backup_bytes())
    copied = Store(restored)
    assert copied.products()[0].price == 7
    assert ReviewStore(copied).items(favorites=True)[0]["note"] == "Preserve me"


def test_personal_preferences_survive_licensed_observation_expiry(tmp_path):
    store = Store(tmp_path / "research.sqlite3")
    p = Product("Best Buy", "Temporary API quote", sku="123", collection_method="bestbuy_api")
    store.add_run("API", [p])
    review = ReviewStore(store)
    review.rate(review.items()[0]["id"], "Love it", "Keep personal note")
    with store.connect() as db:
        db.execute("UPDATE snapshots SET expires_at='2000-01-01T00:00:00+00:00'")
    store.purge_expired()
    assert not review.items(favorites=True)
    assert review.unavailable_preferences(favorites=True)[0]["Personal notes"] == "Keep personal note"


