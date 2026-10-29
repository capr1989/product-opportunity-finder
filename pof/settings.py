"""Validated local defaults. Credentials are deliberately excluded."""
from pof.opportunity_engine import DiscoverySettings, TAXONOMY

DEFAULTS = {"market": "US", "currency": "USD", "business_model": "Explore All", "budget": 500.0,
            "minimum_profit": 5.0, "minimum_margin": 0.0, "quick_queries": 3, "deep_queries": 6,
            "source_limit": 3, "products_per_source": 8, "cache_seconds": 900,
            "categories": [], "excluded_categories": [], "show_images": False, "default_mode": "Quick Scan"}


def get_settings(store):
    return {**DEFAULTS, **(store.get_config("settings", "application") or {})}


def save_settings(store, values):
    if set(values) - set(DEFAULTS):
        raise ValueError("Unsupported setting; credentials never belong in application settings")
    merged = {**get_settings(store), **values}
    if merged["currency"] not in {"USD", "PAB"} or type(merged["cache_seconds"]) is not int or not 0 <= merged["cache_seconds"] <= 900:
        raise ValueError("Unsupported currency or cache duration")
    if not 0 <= merged["minimum_margin"] <= 100:
        raise ValueError("Target margin must be 0–100 percent")
    if any(c not in TAXONOMY for c in merged["excluded_categories"]):
        raise ValueError("Unknown excluded category")
    allowed = [c for c in (merged["categories"] or TAXONOMY) if c not in merged["excluded_categories"]]
    if not allowed:
        raise ValueError("Keep at least one category available for automatic discovery")
    for mode, limit in (("Quick Scan", merged["quick_queries"]), ("Deep Research", merged["deep_queries"])):
        DiscoverySettings(mode=mode, market=merged["market"], business_model=merged["business_model"],
                          budget=merged["budget"], minimum_profit=merged["minimum_profit"],
                          query_limit=limit, source_limit=merged["source_limit"],
                          products_per_source=merged["products_per_source"], categories=tuple(allowed))
    if merged["default_mode"] not in {"Quick Scan", "Deep Research"}:
        raise ValueError("Unsupported default scan mode")
    store.put_config("settings", "application", merged)
    return merged
