"""Deterministic per-unit contribution economics using Decimal arithmetic."""
from dataclasses import dataclass
from decimal import Decimal
import math


@dataclass
class Assumptions:
    duty_rate: float = 0.0
    tax_rate: float = 0.0
    payment_rate: float = 0.029
    payment_fixed: float = 0.30
    platform_rate: float = 0.15
    returns_rate: float = 0.03
    advertising: float = 5.0
    outbound_shipping: float = 0.0
    other_cost: float = 0.0
    conversion_rate: float = 0.02

    def __post_init__(self):
        for key, value in vars(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {key}")
            if key.endswith("rate") and value > 1:
                raise ValueError(f"{key} must be between 0 and 1")


def calculate(cost: float | None, sell: float | None, shipping: float | None,
              moq: float | None, a: Assumptions, currency: str = "USD") -> dict:
    if cost is None or sell is None or shipping is None or moq is None or currency != "USD":
        return {"known": False, "reason": "Need USD cost, sale price, shipping and MOQ"}
    if not all(math.isfinite(v) and v >= 0 for v in (cost, sell, shipping, moq)) or moq < 1:
        raise ValueError("invalid financial input")
    def d(v):
        return Decimal(str(v))
    c, s, freight = map(d, (cost, sell, shipping))
    duty = c * d(a.duty_rate)
    tax = (c + freight + duty) * d(a.tax_rate)
    landed = c + freight + duty + tax
    gross = s - landed
    payment = s * d(a.payment_rate) + d(a.payment_fixed)
    platform = s * d(a.platform_rate)
    returns = s * d(a.returns_rate)
    before_ads = gross - payment - platform - returns - d(a.outbound_shipping) - d(a.other_cost)
    contribution = before_ads - d(a.advertising)
    invested = landed + payment + platform + returns + d(a.outbound_shipping) + d(a.other_cost) + d(a.advertising)
    def ratio(n, denominator):
        return float(n / denominator * 100) if denominator else None
    return {"known": True, "supplier_cost": float(c), "selling_price": float(s), "shipping": float(freight),
            "duty": float(duty), "tax": float(tax), "payment": float(payment), "platform": float(platform),
            "returns": float(returns), "advertising": a.advertising, "landed_cost": float(landed),
            "outbound_shipping": a.outbound_shipping, "other_cost": a.other_cost,
            "gross_profit": float(gross), "contribution_profit": float(contribution),
            "gross_margin": ratio(gross, s), "contribution_margin": ratio(contribution, s),
            "roi": ratio(contribution, invested), "break_even_cac": float(before_ads),
            "break_even_cpc": float(before_ads * d(a.conversion_rate)),
            "quantity": moq, "inventory_commitment": float(landed * d(moq))}
