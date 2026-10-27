"""Provider-neutral bounded catalog search request."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ResearchQuery:
    keywords: str = ""
    category_id: str = ""
    category_name: str = ""
    brand: str = ""
    model: str = ""
    seller: str = ""
    minimum_price: float = 0
    maximum_price: float = 100000
    on_sale: bool = False
    clearance: bool = False
    available_only: bool = True
    target_market: str = "US"
    limit: int = 25
    max_pages: int = 3

    def __post_init__(self):
        for key in ("keywords", "category_id", "category_name", "brand", "model", "seller"):
            value = getattr(self, key)
            if not isinstance(value, str) or len(value) > 200 or any(ord(c) < 32 for c in value):
                raise ValueError("Search text must be at most 200 characters without control characters")
        if not all(math.isfinite(x) and x >= 0 for x in (self.minimum_price, self.maximum_price)):
            raise ValueError("Price limits must be finite and non-negative")
        if self.minimum_price > self.maximum_price:
            raise ValueError("Minimum price must not exceed maximum price")
        if type(self.limit) is not int or not 1 <= self.limit <= 100:
            raise ValueError("Choose 1–100 products per source")
        if type(self.max_pages) is not int or not 1 <= self.max_pages <= 5:
            raise ValueError("Choose 1–5 catalog pages")
        if self.target_market not in {"US", "PA", "US+PA"}:
            raise ValueError("Choose USA, Panama or both")
