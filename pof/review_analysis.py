"""Review evidence and hypothetical scenarios; missing economics stay unknown."""
import math

from pof.opportunity_engine import DiscoverySettings, build_leads
from pof.storage import Store
from pof.matching import normalize
from rapidfuzz.fuzz import token_set_ratio


def monthly_scenario(selling_price, contribution, units):
    if type(units) is not int or not 0 <= units <= 1_000_000:
        raise ValueError("Monthly units must be between 0 and 1,000,000")
    if any(v is not None and (not math.isfinite(v) or (i == 0 and v < 0))
           for i, v in enumerate((selling_price, contribution))):
        raise ValueError("Scenario amounts must be finite")
    return {"monthly_revenue": selling_price * units if selling_price is not None else None,
            "monthly_contribution": contribution * units if contribution is not None else None}


def evidence(items, store, assumptions, context=None):
    universe = {Store.identity(p): p for p in store.products(demo=False)}
    result = {}
    keyword_rows = (store.get_config("keywords", "latest") or {}).get("rows", [])
    mappings = store.configs("keyword_map")
    sessions = sorted(store.configs("discovery_session").values(), key=lambda s: s["created"], reverse=True)
    for item in items:
        p = item["product"]
        mapping = mappings.get(Store.identity(p), {})
        row = next((r for r in keyword_rows if r.get("keyword") == mapping.get("keyword")), None)
        if row:
            p.demand_reference = row.copy()
            p.monthly_searches = row.get("monthly_searches")
            p.states["monthly_searches"] = row.get("status", "unavailable")
        quotes = [q for q in universe.values() if q.source != p.source and q.role == "retailer"]
        quotes.sort(key=lambda q: token_set_ratio(normalize(p.title), normalize(q.title)), reverse=True)
        # Investigate the exact selected snapshot, including its selected variant.
        session = next((s for s in sessions if item["run_id"] in s["run_ids"]), None)
        settings = context or (DiscoverySettings(**session["settings"]) if session else DiscoverySettings())
        leads = build_leads([p, *quotes[:30]], settings, assumptions, store.reviews(), {Store.identity(p)})
        comparisons = [r for r in leads if r["buy_id"] == Store.identity(p) and r.get("sell_id")]
        best = next((r for r in comparisons if r["financial"].get("known")), comparisons[0] if comparisons else None)
        result[item["id"]] = {"comparisons": comparisons, "best": best,
            "financial": best["financial"] if best else {"known": False},
            "confidence": best["match_confidence"] if best else 0,
            "missing": best["missing"] if best else ["Find a comparable retail listing", "Verify selected variant, shipping, costs and fulfillment"],
            "references": [universe[r["sell_id"]] for r in comparisons if r["sell_id"] in universe]}
    return result
