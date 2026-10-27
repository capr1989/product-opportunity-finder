"""Parse explicit schema.org Product JSON-LD; never evaluate website content."""
from html.parser import HTMLParser
import json

from pof.models import Product


class StructuredData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.buffer = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        self.active = tag == "script" and dict(attrs).get("type") == "application/ld+json"

    def handle_data(self, data):
        if self.active:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            try:
                self.documents.append(json.loads("".join(self.buffer)))
            except (ValueError, RecursionError):
                pass
            self.active = False
            self.buffer = []


def parse_products(html: bytes, source: dict) -> list[Product]:
    parser = StructuredData()
    parser.feed(html.decode("utf-8", errors="replace"))
    output = []
    candidates = []
    for doc in parser.documents:
        if isinstance(doc, list):
            candidates.extend(doc)
        elif isinstance(doc, dict):
            candidates.extend(doc.get("@graph", [doc]))
    for item in candidates[:100]:
        if not isinstance(item, dict) or item.get("@type") != "Product":
            continue
        offer = item.get("offers", {})
        if isinstance(offer, list):
            offer = offer[0] if len(offer) == 1 else {}
        if not isinstance(offer, dict):
            offer = {}
        brand = item.get("brand", "")
        rating = item.get("aggregateRating", {})
        values = {"source": source["name"], "role": source["role"], "title": item.get("name", ""),
            "url": source["url"], "brand": brand.get("name", "") if isinstance(brand, dict) else brand,
            "model": item.get("model", ""), "sku": item.get("sku", ""),
            "gtin": str(item.get("gtin13", item.get("gtin", ""))),
            "price": offer.get("price"), "currency": offer.get("priceCurrency", "UNKNOWN"),
            "availability": str(offer.get("availability", "unknown")).split("/")[-1],
            "rating": rating.get("ratingValue"), "reviews": rating.get("reviewCount")}
        values["states"] = {k: "verified" for k, v in values.items() if v is not None and v != ""}
        output.append(Product(**values))
    if not output:
        raise ValueError("No supported Product JSON-LD. Use an authorized feed or CSV import")
    return output
