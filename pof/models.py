"""Validated normalized product snapshots with per-field provenance."""
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
import math
from typing import Any
from urllib.parse import urlsplit


def now() -> str:
    return datetime.now(UTC).isoformat()


NUMERIC = {"price", "original_price", "shipping", "delivery_days", "moq", "weight_kg",
           "rating", "reviews", "monthly_searches", "competition_index", "cpc", "low_bid", "high_bid"}


@dataclass
class Product:
    source: str
    title: str
    role: str = "retailer"
    url: str = ""
    brand: str = ""
    model: str = ""
    gtin: str = ""
    sku: str = ""
    category: str = ""
    subcategory: str = ""
    condition: str = "new"
    currency: str = "USD"
    price: float | None = None
    original_price: float | None = None
    shipping: float | None = None
    delivery_days: float | None = None
    moq: float | None = None
    weight_kg: float | None = None
    availability: str = "unknown"
    merchant: str = ""
    supplier_country: str = ""
    target_country: str = "US"
    rating: float | None = None
    reviews: float | None = None
    fragile: bool | None = None
    restricted: bool | None = None
    monthly_searches: float | None = None
    trend: str = ""
    competition: str = ""
    competition_index: float | None = None
    cpc: float | None = None
    low_bid: float | None = None
    high_bid: float | None = None
    seasonality: str = ""
    demand_confidence: str = ""
    specs: dict = field(default_factory=dict)
    states: dict = field(default_factory=dict)
    collected_at: str = field(default_factory=now)
    image_url: str = ""
    image_reuse_permitted: bool = False
    demo: bool = False

    def __post_init__(self) -> None:
        string_fields = {"source", "title", "role", "url", "brand", "model", "gtin", "sku", "category",
            "subcategory", "condition", "currency", "availability", "merchant", "supplier_country",
            "target_country", "trend", "competition", "seasonality", "demand_confidence", "collected_at", "image_url"}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name in string_fields and not isinstance(value, str):
                raise ValueError(f"{f.name} must be text")
            if isinstance(value, str) and len(value) > 4000:
                raise ValueError(f"{f.name}: maximum length 4000")
        if not self.source.strip() or not self.title.strip():
            raise ValueError("source and title are required")
        if self.role not in {"supplier", "retailer"}:
            raise ValueError("role must be supplier or retailer")
        for name in NUMERIC:
            value = getattr(self, name)
            if value is not None:
                value = float(value)
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"{name} must be finite and non-negative")
                setattr(self, name, value)
        if self.moq is not None and (self.moq < 1 or not self.moq.is_integer()):
            raise ValueError("moq must be a positive integer")
        if self.rating is not None and self.rating > 5:
            raise ValueError("rating must be 0–5")
        for name in ("fragile", "restricted", "demo", "image_reuse_permitted"):
            if getattr(self, name) is not None and type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean or unknown")
        if not isinstance(self.specs, dict) or not isinstance(self.states, dict):
            raise ValueError("specs and states must be objects")
        if any(v not in {"verified", "estimated", "unavailable", "stale"} for v in self.states.values()):
            raise ValueError("invalid field state")
        stamp = datetime.fromisoformat(self.collected_at)
        if stamp.tzinfo is None or stamp > datetime.now(UTC):
            raise ValueError("collected_at must be timezone-aware and not in the future")
        for value in (self.url, self.image_url):
            if value:
                u = urlsplit(value)
                if u.scheme != "https" or not u.hostname or u.username or u.password:
                    raise ValueError("product links must be HTTPS without credentials")

    def state(self, name: str, stale_days: int = 7) -> str:
        value = getattr(self, name, None)
        if value is None or value == "" or value == "unknown":
            return "unavailable"
        age = (datetime.now(UTC) - datetime.fromisoformat(self.collected_at)).days
        return "stale" if age >= stale_days else self.states.get(name, "estimated")

    def record(self) -> dict[str, Any]:
        return asdict(self)
