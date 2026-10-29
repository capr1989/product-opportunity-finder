"""Additive review schema and personal curation; original snapshots stay authoritative."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from pof.matching import variants
from pof.models import Product, now

RATINGS = ("Unrated", "Love it", "Like", "Maybe later", "Pass")


def candidate_id(product, original_identity):
    # Known variants remain separate, even when a merchant reuses a listing URL.
    variant = {k: v for k, v in variants(product).items()
               if k in {"color", "colour", "size", "material", "dimensions", "pack", "gb", "tb", "ml", "oz", "inch"}}
    if product.model:
        variant["model"] = product.model.strip().casefold()
    if product.gtin:
        variant["gtin"] = product.gtin
    stable = [product.source, product.role, product.sku, product.demo] if product.sku else original_identity
    return hashlib.sha256(json.dumps([stable, variant], sort_keys=True).encode()).hexdigest()


def associate(db, snapshot_id, run_id, identity, product):
    cid = candidate_id(product, identity)
    lid = hashlib.sha256((identity + cid).encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO candidates VALUES(?,?)", (cid, now()))
    db.execute("INSERT OR IGNORE INTO listings VALUES(?,?,?,?,?)",
               (lid, cid, identity, product.source, product.role))
    db.execute("INSERT OR IGNORE INTO observations VALUES(?,?)", (snapshot_id, lid))
    db.execute("INSERT OR IGNORE INTO scan_products VALUES(?,?,?)", (run_id, cid, snapshot_id))


def migrate(store):
    with store.connect() as db:
        if db.execute("SELECT 1 FROM migrations WHERE version=3").fetchone():
            return
    # SQLite's backup API includes committed WAL contents. Failure aborts migration.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup = store.path.with_name(store.path.stem + ".pre-review-v3." + stamp + ".sqlite3")
    with sqlite3.connect(store.path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    statements = [
        "CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,created TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL REFERENCES candidates(id),original_identity TEXT NOT NULL,source TEXT NOT NULL,role TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS observations(snapshot_id INTEGER PRIMARY KEY REFERENCES snapshots(id) ON DELETE CASCADE,listing_id TEXT NOT NULL REFERENCES listings(id))",
        "CREATE TABLE IF NOT EXISTS scan_products(run_id INTEGER REFERENCES runs(id),candidate_id TEXT REFERENCES candidates(id),snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,PRIMARY KEY(run_id,snapshot_id))",
        "CREATE TABLE IF NOT EXISTS product_ratings(candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),rating TEXT NOT NULL CHECK(rating IN ('Unrated','Love it','Like','Maybe later','Pass')),updated TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS product_notes(candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),note TEXT NOT NULL,updated TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS favorites(candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),created TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS investigations(candidate_id TEXT REFERENCES candidates(id),session_id TEXT NOT NULL,PRIMARY KEY(candidate_id,session_id))",
        "CREATE INDEX IF NOT EXISTS scan_candidates ON scan_products(candidate_id,run_id)",
    ]
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for statement in statements:
            db.execute(statement)
        for sid, rid, identity, payload in db.execute("SELECT id,run_id,identity,payload FROM snapshots").fetchall():
            associate(db, sid, rid, identity, Product(**json.loads(payload)))
        db.execute("INSERT INTO migrations VALUES(3,?)", (now(),))


class ReviewStore:
    def __init__(self, store):
        self.store = store

    def rate(self, cid, rating, note=None):
        if rating not in RATINGS:
            raise ValueError("Choose a supported personal rating")
        if note is not None and (not isinstance(note, str) or len(note) > 10000):
            raise ValueError("Notes must contain at most 10,000 characters")
        with self.store.connect() as db:
            if not db.execute("SELECT 1 FROM candidates WHERE id=?", (cid,)).fetchone():
                raise ValueError("Product is no longer available for review")
            db.execute("INSERT INTO product_ratings VALUES(?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET rating=excluded.rating,updated=excluded.updated", (cid, rating, now()))
            if note is not None:
                db.execute("INSERT INTO product_notes VALUES(?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET note=excluded.note,updated=excluded.updated", (cid, note, now()))
            if rating in {"Love it", "Like"}:
                db.execute("INSERT OR IGNORE INTO favorites VALUES(?,?)", (cid, now()))
            else:
                db.execute("DELETE FROM favorites WHERE candidate_id=?", (cid,))

    def items(self, run_ids=(), favorites=False, watchlist=False):
        self.store.purge_expired()
        with self.store.connect() as db:
            where, args = "", []
            if run_ids:
                where = " WHERE s.run_id IN (" + ",".join("?" for _ in run_ids) + ")"
                args = list(run_ids)
            rows = db.execute("SELECT c.id,s.id,s.run_id,s.payload,COALESCE(r.rating,'Unrated'),COALESCE(n.note,'') "
                "FROM candidates c JOIN listings l ON l.candidate_id=c.id JOIN observations o ON o.listing_id=l.id "
                "JOIN snapshots s ON s.id=o.snapshot_id LEFT JOIN product_ratings r ON r.candidate_id=c.id "
                "LEFT JOIN product_notes n ON n.candidate_id=c.id" + where + " ORDER BY s.id DESC", args).fetchall()
        result = {}
        for cid, sid, rid, payload, rating, note in rows:
            if cid in result or (favorites and rating not in {"Love it", "Like"}) or (watchlist and rating != "Maybe later"):
                continue
            p = Product(**json.loads(payload))
            if not p.demo:
                result[cid] = {"id": cid, "snapshot_id": sid, "run_id": rid, "product": p,
                               "rating": rating, "note": note}
        return list(result.values())

    def history(self, cid):
        with self.store.connect() as db:
            rows = db.execute("SELECT s.run_id,s.payload FROM observations o JOIN listings l ON l.id=o.listing_id JOIN snapshots s ON s.id=o.snapshot_id WHERE l.candidate_id=? ORDER BY s.id", (cid,)).fetchall()
        return [{"scan": rid, "collected_at": p["collected_at"], "price": p["price"],
                 "shipping": p["shipping"], "currency": p["currency"]} for rid, payload in rows for p in [json.loads(payload)]]
