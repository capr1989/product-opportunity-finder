"""Search, comparison, verified-reference deals and ranked opportunities."""
from dataclasses import asdict
import hashlib

from pof.finance import Assumptions, calculate
from pof.matching import match, normalize
from pof.models import Product
from pof.scoring import DEFAULT_WEIGHTS, score
from pof.storage import Store


def search(products: list[Product], query: str) -> list[Product]:
    tokens = normalize(query).split()
    return [p for p in products if all(t in normalize(" ".join(
        [p.title, p.brand, p.model, p.gtin, p.category, p.sku])) for t in tokens)]


def pair_id(a: Product, b: Product) -> str:
    return hashlib.sha256((Store.identity(a) + Store.identity(b)).encode()).hexdigest()


def opportunities(products: list[Product], assumptions: Assumptions, weights=None,
                  reviews=None, dropship: bool = False) -> list[dict]:
    if len(products) > 1000:
        raise ValueError("Limit analysis to 1,000 products using category/search filters")
    reviews = reviews or {}
    rows = []
    buyers = [p for p in products if p.role == "retailer"]
    sources = [p for p in products if p.role == "supplier" or not dropship]
    for source in sources:
        for retail in buyers:
            if source is retail or source.source == retail.source or source.demo != retail.demo:
                continue
            m = match(source, retail)
            if m.confidence < 40:
                continue
            pair = pair_id(source, retail)
            decision = reviews.get(pair, {}).get("decision", "automatic")
            if decision == "reject":
                continue
            accepted = m.kind in {"exact", "equivalent"} or decision == "approve"
            currencies = source.currency == retail.currency == "USD"
            financial = calculate(source.price, retail.price if accepted and currencies else None,
                                  source.shipping, source.moq, assumptions,
                                  source.currency if currencies else "UNKNOWN")
            ranking, breakdown = score(source, financial, m.confidence, weights or DEFAULT_WEIGHTS)
            record = source.record()
            record.update(financial)
            record.update({"pair": pair, "retailer": retail.source, "retail_title": retail.title,
                "retail_url": retail.url, "match_kind": m.kind, "match_confidence": m.confidence,
                "match_reason": m.reason, "review": decision, "score": ranking, "breakdown": breakdown,
                "source_record": source.record(), "retail_record": retail.record(),
                "assumptions": asdict(assumptions), "profit_status": "estimated" if financial["known"] else "unavailable"})
            rows.append(record)
    return sorted(rows, key=lambda r: r["score"], reverse=True)


def deals(products: list[Product]) -> list[dict]:
    rows = []
    for p in products:
        if p.role != "retailer" or p.price is None:
            continue
        # A different merchant's current, verified, exact-match quote is an independent reference.
        refs = [r for r in products if r.role == "retailer" and r.source != p.source
                and r.demo == p.demo and r.price is not None and r.currency == p.currency
                and r.state("price") == "verified" and p.state("price") == "verified"
                and match(p, r).kind == "exact" and r.price > p.price]
        if refs:
            ref = min(refs, key=lambda x: x.price)
            row = p.record()
            row.update(reference_price=ref.price, reference_source=ref.source, reference_url=ref.url,
                       verified_discount=(ref.price - p.price) / ref.price * 100,
                       reference_timestamp=ref.collected_at)
            rows.append(row)
    return sorted(rows, key=lambda x: x["verified_discount"], reverse=True)
