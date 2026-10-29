"""Live-first orchestration with source isolation and no demo fallback."""
from dataclasses import asdict
import hashlib
import json
import time
from pathlib import Path
import traceback
from typing import Callable

from pof.connectors import collect
from pof.live.bestbuy import BestBuyConnector
from pof.live.catalog import bestbuy_browser_mode, record_attempt
from pof.live.errors import SourceError
from pof.live.query import ResearchQuery
from pof.models import Product
from pof.research import search


def keep_product(p: Product, query: ResearchQuery) -> bool:
    if p.demo:
        return False
    if query.minimum_price > 0 or query.maximum_price < 100000:
        if p.price is None or not query.minimum_price <= p.price <= query.maximum_price:
            return False
    if query.brand and query.brand.casefold() not in (p.brand or p.title).casefold():
        return False
    if query.model and query.model.casefold() not in (p.model or p.title).casefold():
        return False
    if query.seller and query.seller.casefold() not in p.merchant.casefold():
        return False
    if query.on_sale and p.source_attributes.get("on_sale") is not True:
        return False
    if query.clearance and p.source_attributes.get("clearance") is not True:
        return False
    if query.available_only and p.availability != "in_stock":
        return False
    if p.collection_method in {"bestbuy_api", "bestbuy_browser", "amazon_public", "aliexpress_public"}:
        return True  # Provider keyword search already ran; do not discard localized/relevant titles.
    return bool(search([p], query.keywords))


def discover_bestbuy(query, store, key, *, refresh=True, http=None):
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    cache_key = "bestbuy-live:" + hashlib.sha256(json.dumps([asdict(query), fingerprint], sort_keys=True).encode()).hexdigest()
    if not refresh:
        with store.connect() as db:
            row = db.execute("SELECT payload,created FROM cache WHERE key=?", (cache_key,)).fetchone()
        if row and time.time() - row[1] < 900:
            return [Product(**p) for p in json.loads(row[0])], True
    with store.connect() as db:
        previous = db.execute("SELECT created FROM cache WHERE key='bestbuy-cooldown'").fetchone()
        if previous and time.time() - previous[0] < 1:
            raise SourceError("cooldown", "Please wait a moment before contacting Best Buy again.")
        db.execute("INSERT OR REPLACE INTO cache VALUES('bestbuy-cooldown','{}',?)", (time.time(),))
    products = BestBuyConnector(key, http).discover(query)
    with store.connect() as db:
        db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (cache_key, json.dumps([p.record() for p in products]), time.time()))
    return products, False


def run_research(query: ResearchQuery, names: list[str], store, credentials: dict,
                 progress: Callable | None = None, refresh=True, http=None) -> dict:
    if not names or len(names) > 10 or len(set(names)) != len(names):
        raise ValueError("Choose 1–10 different sources")
    start = time.monotonic()
    products, reports = [], []
    for index, name in enumerate(names):
        if progress:
            progress(index / len(names), f"Collecting {name}…", len(products))
        config = store.get_config("source", name)
        try:
            if not config or not config.get("enabled", True):
                raise SourceError("disabled", "This source is disabled. Enable it in Source Manager.")
            if config.get("kind") == "browser_catalog":
                from pof.live.browser_catalog import discover_browser
                found, cached = discover_browser(config, query, http=http), False
            elif config.get("kind") in {"csv", "json", "browser", "public_page"}:
                found, cached = collect(config, store, refresh)
            elif name == "Best Buy":
                key = credentials.get("BESTBUY_API_KEY", "")
                mode = config.get("bestbuy_method", "api" if key else "browser")
                if bestbuy_browser_mode(config, bool(key)):
                    from pof.live.bestbuy_browser import BestBuyBrowserConnector
                    try:
                        found, cached = BestBuyBrowserConnector().discover(query), False
                    except SourceError as exc:
                        if mode == "browser-first" and key and exc.code == "browser_missing":
                            found, cached = discover_bestbuy(query, store, key, refresh=refresh, http=http)
                        else:
                            raise
                elif key:
                    found, cached = discover_bestbuy(query, store, key, refresh=refresh, http=http)
                else:
                    raise SourceError("credentials_required", "Optional Best Buy API mode needs a key. Choose public browser mode in Source Manager to run without one.")
            elif name in {"Amazon US", "AliExpress"}:
                from pof.live.public_catalogs import AmazonPublicConnector, AliExpressPublicConnector
                connector = AmazonPublicConnector(http) if name == "Amazon US" else AliExpressPublicConnector(http)
                found, cached = connector.discover(query), False
            else:
                raise SourceError("not_connected", "This source has no verified live catalog connector yet. See Source Manager for access details.")
            found = [p for p in found if keep_product(p, query)][:query.limit]
            products.extend(found)
            record_attempt(store, name, count=len(found), live=not cached)
            reports.append({"source": name, "products": len(found), "priced_products": sum(p.price is not None for p in found), "status": "cached" if cached else "live request",
                            "error": "", "code": ""})
        except Exception as exc:
            message = str(exc) if isinstance(exc, SourceError) else "Collection could not finish safely. Check source settings, network access and provider permissions."
            code = exc.code if isinstance(exc, SourceError) else "collection_failed"
            record_attempt(store, name, error=message, code=code)
            if not isinstance(exc, SourceError):
                # Type/location only: raw exception text can contain credential-bearing URLs.
                frames = traceback.extract_tb(exc.__traceback__)
                store.put_config("collection_diagnostic", name, {"exception_type": type(exc).__name__,
                    "locations": [f"{Path(frame.filename).name}:{frame.lineno}" for frame in frames[-4:]]})
            reports.append({"source": name, "products": 0, "status": "failed", "error": message, "code": code})
        if progress:
            progress((index + 1) / len(names), f"Finished {name}", len(products))
    run_id = store.add_run("Live research: " + (query.keywords or query.category_name or "catalog discovery"), products)
    summary = {"run_id": run_id, "reports": reports, "elapsed_seconds": round(time.monotonic() - start, 2),
               "products_found": len(products), "query": asdict(query), "demo": False}
    store.put_config("live_run", str(run_id), summary)
    return summary
