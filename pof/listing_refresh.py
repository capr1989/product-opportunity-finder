"""Refresh a single public listing's explicit offer without guessing a match."""
from dataclasses import replace
from urllib.parse import urlsplit

from pof.extraction import parse_products
from pof.live.errors import SourceError
from pof.models import NUMERIC, now
from pof.security import SafeHTTP

HOSTS = {"Best Buy": "www.bestbuy.com", "Amazon US": "www.amazon.com", "AliExpress": "www.aliexpress.com"}


def refresh_listing(product, store, http=None):
    host = HOSTS.get(product.source)
    if not host or urlsplit(product.url).hostname != host or product.retention_hours or product.collection_method == "bestbuy_api":
        raise SourceError("refresh_unavailable", "Use Source Manager to refresh this source; direct public-listing refresh is unavailable.")
    raw = (http or SafeHTTP(2)).fetch(product.url, host, ("text/html", "application/xhtml+xml"))
    try:
        offers = parse_products(raw, {"name": product.source, "role": product.role, "url": product.url})
    except (ValueError, TypeError, KeyError):
        raise SourceError("price_unavailable", "The public page did not provide a readable product offer. Open the listing to check its price.") from None
    matched = [p for p in offers if p.price is not None and (
        (product.sku and p.sku == product.sku) or (product.gtin and p.gtin == product.gtin))]
    if len(matched) != 1:
        raise SourceError("price_unavailable", "A price for this exact product could not be confirmed. Open the listing to check its current offer.")
    found = matched[0]
    states = dict(product.states)
    # Preserve identity/notes and append a quote; other old observations are not
    # silently made fresh by refreshing price alone.
    for field in NUMERIC | {"availability", "condition"}:
        if getattr(product, field, None) is not None:
            states[field] = "stale"
    states.update(price="verified", currency="verified" if len(found.currency) == 3 else "unavailable")
    availability = product.availability
    if found.availability in {"in_stock", "out_of_stock", "preorder"}:
        availability = found.availability
        states["availability"] = "verified"
    stamp = now()
    refreshed = replace(product, price=found.price, currency=found.currency, availability=availability,
                        collected_at=stamp, states=states,
                        source_attributes={**product.source_attributes,
                            "other_details_collected_at": product.source_attributes.get("other_details_collected_at", product.collected_at),
                            "price_refresh_method": "Public listing Product JSON-LD"})
    store.add_run("Refreshed listing: " + product.title[:160], [refreshed])
    return refreshed
