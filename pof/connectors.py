"""Interchangeable source adapters. No retailer access is implied by source registration."""
from dataclasses import fields
import hashlib
import json
from typing import Protocol
import time

from pof.extraction import parse_products
from pof.importing import import_csv
from pof.models import Product
from pof.security import SafeHTTP, validate_url
from pof.storage import Store


class Connector(Protocol):
    def collect(self, source: dict, http: SafeHTTP) -> list[Product]: ...


class FeedConnector:
    def collect(self, source, http):
        raw = http.fetch(source["url"], source["allowed_host"])
        if source["kind"] == "csv":
            products = import_csv(raw)
        else:
            try:
                rows = json.loads(raw)
                if not isinstance(rows, list) or len(rows) > 10000:
                    raise ValueError("Expected at most 10,000 normalized product objects")
                allowed = {f.name for f in fields(Product)}
                products = []
                for row in rows:
                    if not isinstance(row, dict) or set(row) - allowed:
                        raise ValueError("Feed contains unsupported fields")
                    products.append(Product(**{**row, "source": source["name"], "role": source["role"], "demo": False}))
            except (TypeError, RecursionError, json.JSONDecodeError):
                raise ValueError("Malformed normalized JSON feed") from None
        for p in products:
            p.source, p.role, p.demo = source["name"], source["role"], False
        return products


class PublicPageConnector:
    def collect(self, source, http):
        if source["kind"] == "browser":
            from pof.browser import extract_page
            raw = extract_page(source["url"], source["allowed_host"], http)
        else:
            raw = http.fetch(source["url"], source["allowed_host"], ("text/html", "application/xhtml+xml"))
        # Stop if the document presents a barrier; never solve challenges.
        if any(x in raw.lower() for x in (b"captcha", b"access denied", b"verify you are human")):
            raise ValueError("Access barrier detected; use authorized API/feed/import")
        return parse_products(raw, source)


REGISTRY = {"csv": FeedConnector(), "json": FeedConnector(),
            "public_page": PublicPageConnector(), "browser": PublicPageConnector()}


def status(source: dict) -> str:
    if not source.get("enabled"):
        return "disabled"
    if source.get("kind") == "import":
        return "import-only — provider API/automation access not configured"
    if not source.get("permission_confirmed"):
        return "restricted — confirm provider permission before collection"
    if not source.get("url") or not source.get("allowed_host"):
        return "requires configuration — authorized endpoint and host required"
    return "configured — live operation unverified until successful collection"


def collect(source: dict, store: Store, refresh: bool = False) -> tuple[list[Product], bool]:
    if not status(source).startswith("configured"):
        raise ValueError(status(source))
    validate_url(source["url"], source["allowed_host"])
    key = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    with store.connect() as db:
        cached = db.execute("SELECT payload,created FROM cache WHERE key=?", (key,)).fetchone()
    if cached and not refresh and time.time() - cached[1] < source.get("cache_seconds", 3600):
        return [Product(**row) for row in json.loads(cached[0])], True
    # Persisted cooldown prevents repeated UI actions bypassing per-source pacing.
    rate_key = "source-rate:" + source["name"]
    with store.connect() as db:
        last = db.execute("SELECT created FROM cache WHERE key=?", (rate_key,)).fetchone()
        wait = source.get("interval", 2)
        if last and time.time() - last[0] < wait:
            raise ValueError("Source cooldown active; wait before retrying")
        db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (rate_key, "{}", time.time()))
    adapter = REGISTRY.get(source["kind"])
    if adapter is None:
        raise ValueError("Unknown connector kind")
    products = adapter.collect(source, SafeHTTP(interval=source.get("interval", 2)))
    with store.connect() as db:
        db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)",
                   (key, json.dumps([p.record() for p in products]), time.time()))
    return products, False
