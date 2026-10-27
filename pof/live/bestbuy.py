"""Official Best Buy Products API: bounded keyword/category catalog discovery."""
import json
import logging
import re
from urllib.parse import urlsplit

from pof.live.errors import SourceError
from pof.live.query import ResearchQuery
from pof.models import Product
from pof.security import SafeHTTP

HOST = "api.bestbuy.com"
SHOW = "sku,name,salePrice,regularPrice,url,image,manufacturer,modelNumber,upc,categoryPath,onlineAvailability,shippingCost,onSale,clearance,customerReviewAverage,customerReviewCount,condition"


def text_value(value: str) -> str:
    if not re.fullmatch(r"[\w .,'+/-]{1,200}", value, re.UNICODE) or any(c in value for c in "'\"()&=<>*"):
        raise ValueError("Use plain search words, brand or model names without query operators")
    return '"' + value + '"'


def safe_link(value, allowed_hosts) -> str:
    if not isinstance(value, str):
        return ""
    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.hostname in allowed_hosts and not parsed.username and not parsed.password:
        return value
    return ""


class BestBuyConnector:
    def __init__(self, api_key: str, http: SafeHTTP | None = None):
        if not api_key or not api_key.strip():
            raise SourceError("credentials_required", "Best Buy requires an API key. Open Source Manager → Best Buy → Get API Key.")
        if len(api_key) > 512 or any(c.isspace() for c in api_key):
            raise SourceError("credentials_invalid", "Check your Best Buy API key: it must not contain spaces or line breaks.")
        self._api_key = api_key
        self.http = http or SafeHTTP(1)
        # HTTPX's informational request logger includes query strings. Best Buy keys
        # must be sent in the query, so request-level library logging is disabled.
        logging.getLogger("httpx").disabled = True
        logging.getLogger("httpcore").disabled = True

    @staticmethod
    def expression(query: ResearchQuery) -> str:
        terms = ["active=true", "type=HardGood", f"salePrice>={query.minimum_price:g}", f"salePrice<={query.maximum_price:g}"]
        if query.available_only:
            terms.append("onlineAvailability=true")
        if query.keywords:
            for token in query.keywords.split():
                terms.append("search=" + text_value(token))
        if query.category_id:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", query.category_id):
                raise ValueError("Choose a valid catalog category")
            terms.append("categoryPath.id=" + query.category_id)
        if query.category_name:
            terms.append("categoryPath.name=" + text_value(query.category_name))
        for field, value in (("manufacturer", query.brand), ("modelNumber", query.model)):
            if value:
                terms.append(field + "=" + text_value(value))
        if query.on_sale:
            terms.append("onSale=true")
        if query.clearance:
            terms.append("clearance=true")
        return "&".join(terms)

    def discover(self, query: ResearchQuery) -> list[Product]:
        if query.seller and query.seller.casefold() not in {"best buy", "bestbuy"}:
            return []
        expression = self.expression(query)
        products = []
        seen = set()
        for page in range(1, query.max_pages + 1):
            raw = self.http.fetch(f"https://{HOST}/v1/products({expression})", HOST,
                params={"apiKey": self._api_key, "format": "json", "show": SHOW,
                        "pageSize": min(query.limit, 100), "page": page, "sort": "salePrice.asc"})
            try:
                data = json.loads(raw)
                records = data["products"]
                if not isinstance(records, list) or len(records) > 100:
                    raise ValueError("Bad product list")
                for row in records:
                    p = self.normalize(row, query.target_market)
                    if p.sku not in seen:
                        products.append(p)
                        seen.add(p.sku)
                    if len(products) >= query.limit:
                        return products
                if not records or page >= int(data.get("totalPages", page)):
                    break
            except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
                raise SourceError("invalid_product_data", "Best Buy returned incomplete or unexpected product information. No sample data was substituted.") from None
        return products

    @staticmethod
    def normalize(row: dict, market: str) -> Product:
        if not isinstance(row, dict) or not row.get("sku") or not row.get("name"):
            raise ValueError("Missing product identity")
        categories = row.get("categoryPath") or []
        names = [c["name"] for c in categories if isinstance(c, dict) and isinstance(c.get("name"), str)]
        names = [name for name in names if name.lower() != "best buy"]
        availability = "unknown"
        if row.get("onlineAvailability") is True:
            availability = "in_stock"
        elif row.get("onlineAvailability") is False:
            availability = "out_of_stock"
        url = safe_link(row.get("url"), {"api.bestbuy.com", "www.bestbuy.com", "bestbuy.com"})
        if not url:
            raise ValueError("Missing valid product listing URL")
        image = safe_link(row.get("image"), {"pisces.bbystatic.com", "pisces.bbystatic.com.edgesuite.net", "images.bestbuy.com"})
        p = Product("Best Buy", row["name"], role="retailer", url=url,
            sku=str(row["sku"]), brand=row.get("manufacturer") or "", model=row.get("modelNumber") or "",
            gtin=str(row.get("upc") or ""), price=row.get("salePrice"), original_price=row.get("regularPrice"),
            category=names[0] if names else "", subcategory=names[-1] if len(names) > 1 else "",
            currency="USD", condition=(row.get("condition") or "unknown").lower(), shipping=row.get("shippingCost"), moq=1, availability=availability,
            merchant="Best Buy", supplier_country="US", target_country=market,
            rating=row.get("customerReviewAverage"), reviews=row.get("customerReviewCount"),
            image_url=image, image_reuse_permitted=bool(image), collection_method="bestbuy_api", retention_hours=72,
            source_attributes={"on_sale": row.get("onSale"), "clearance": row.get("clearance"),
                "delivery_to_target": "unverified" if market != "US" else "Confirm delivery for your ZIP code",
                "reference_price_status": "advertised regular price; not independently verified"})
        p.states = {k: "verified" for k, v in p.record().items() if v is not None and v != ""}
        p.states["target_country"] = "estimated"
        p.states["moq"] = "estimated"
        return p
