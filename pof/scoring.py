"""Transparent bounded scores. Missing factors score zero, with no weight redistribution."""
from datetime import UTC, datetime
import math

from pof.models import Product

DEFAULT_WEIGHTS = {"profitability": 30, "demand": 20, "competition": 10, "fulfillment": 10,
                   "reliability": 5, "match": 15, "freshness": 5, "risk": 5}


def score(p: Product, financial: dict, confidence: float, weights: dict) -> tuple[float, dict]:
    if set(weights) != set(DEFAULT_WEIGHTS) or any(not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError("Invalid scoring weights")
    age = max(0, (datetime.now(UTC) - datetime.fromisoformat(p.collected_at)).total_seconds() / 86400)
    factors = {
        "profitability": min(100, max(0, (financial.get("contribution_margin") or 0) * 2)),
        "demand": min(100, math.log10(1 + (p.monthly_searches or 0)) * 20)
            if p.state("monthly_searches") == "verified" else 0,
        "competition": 100 - min(100, p.competition_index) if p.competition_index is not None else 0,
        "fulfillment": max(0, 100 - p.delivery_days * 4) if p.delivery_days is not None else 0,
        "reliability": min(100, (p.rating or 0) * 20) if p.reviews and p.reviews >= 10 else 0,
        "match": confidence,
        "freshness": max(0, 100 - age * 100 / 30),
        "risk": 100 if p.fragile is False and p.restricted is False and financial.get("known") else 0,
    }
    denominator = sum(weights.values())
    breakdown = {key: {"factor": round(value, 2), "weight": weights[key],
                     "points": round(value * weights[key] / denominator, 2) if denominator else 0}
                 for key, value in factors.items()}
    return round(sum(v["points"] for v in breakdown.values()), 2), breakdown
