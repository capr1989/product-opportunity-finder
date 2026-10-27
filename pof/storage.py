"""Versioned SQLite persistence. Every collection appends immutable snapshots."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from pof.models import Product, now

SOURCES = ["Alibaba", "AliExpress", "CJdropshipping", "Amazon US", "eBay US", "Walmart",
           "Best Buy", "Target", "Costco", "Home Depot", "Lowe's", "Newegg", "Macy's", "Kohl's"]


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, name TEXT, created TEXT);
                CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY, run_id INTEGER,
                    identity TEXT, payload TEXT, created TEXT, FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE INDEX IF NOT EXISTS identity_time ON snapshots(identity, id);
                CREATE TABLE IF NOT EXISTS saved(identity TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS config(kind TEXT, name TEXT, payload TEXT, PRIMARY KEY(kind,name));
                CREATE TABLE IF NOT EXISTS reviews(pair TEXT PRIMARY KEY, decision TEXT, note TEXT);
                CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, payload TEXT, created REAL);
            """)
            db.execute("INSERT OR IGNORE INTO migrations VALUES(1,?)", (now(),))
        for index, name in enumerate(SOURCES):
            if self.get_config("source", name) is None:
                self.put_config("source", name, {"name": name, "role": "supplier" if index < 3 else "retailer",
                    "enabled": True, "kind": "import", "url": "", "allowed_host": "",
                    "permission_confirmed": False, "interval": 2.0, "cache_seconds": 3600})

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def identity(p: Product) -> str:
        key = [p.source, p.role, p.url or p.sku or f"{p.brand}|{p.model}|{p.title}", p.demo]
        return hashlib.sha256(json.dumps(key).encode()).hexdigest()

    def add_run(self, name: str, products: list[Product]) -> int:
        for p in products:
            if not p.demo and self.get_config("source", p.source) is None:
                self.put_config("source", p.source, {"name": p.source, "role": p.role, "enabled": True,
                    "kind": "import", "url": "", "allowed_host": "", "permission_confirmed": False,
                    "interval": 2.0, "cache_seconds": 3600})
        with self.connect() as db:
            run_id = db.execute("INSERT INTO runs(name,created) VALUES(?,?)", (name[:200], now())).lastrowid
            for p in products:
                db.execute("INSERT INTO snapshots(run_id,identity,payload,created) VALUES(?,?,?,?)",
                           (run_id, self.identity(p), json.dumps(p.record()), now()))
        return run_id

    def products(self, run_id: int | None = None, demo: bool | None = None) -> list[Product]:
        with self.connect() as db:
            if run_id is None:
                rows = db.execute("SELECT payload FROM snapshots WHERE id IN "
                                  "(SELECT MAX(id) FROM snapshots GROUP BY identity)").fetchall()
            else:
                rows = db.execute("SELECT payload FROM snapshots WHERE run_id=?", (run_id,)).fetchall()
        products = [Product(**json.loads(row[0])) for row in rows]
        return [p for p in products if demo is None or p.demo == demo]

    def history(self):
        with self.connect() as db:
            return db.execute("SELECT r.id,r.name,r.created,COUNT(s.id) FROM runs r LEFT JOIN snapshots s "
                              "ON s.run_id=r.id GROUP BY r.id ORDER BY r.id DESC").fetchall()

    def price_history(self, p: Product):
        with self.connect() as db:
            rows = db.execute("SELECT run_id,payload,created FROM snapshots WHERE identity=? ORDER BY id",
                              (self.identity(p),)).fetchall()
        return [{"run_id": r[0], "price": json.loads(r[1])["price"], "collected_at": r[2]} for r in rows]

    def put_config(self, kind: str, name: str, value: dict):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO config VALUES(?,?,?)", (kind, name[:200], json.dumps(value)))

    def get_config(self, kind: str, name: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM config WHERE kind=? AND name=?", (kind, name)).fetchone()
        return json.loads(row[0]) if row else None

    def configs(self, kind: str):
        with self.connect() as db:
            rows = db.execute("SELECT name,payload FROM config WHERE kind=? ORDER BY name", (kind,)).fetchall()
        return {name: json.loads(value) for name, value in rows}

    def save(self, p: Product):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO saved VALUES(?)", (self.identity(p),))

    def saved(self):
        with self.connect() as db:
            return {r[0] for r in db.execute("SELECT identity FROM saved")}

    def review(self, pair: str, decision: str, note: str):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO reviews VALUES(?,?,?)", (pair, decision, note[:2000]))

    def reviews(self):
        with self.connect() as db:
            return {r[0]: {"decision": r[1], "note": r[2]} for r in db.execute("SELECT * FROM reviews")}
