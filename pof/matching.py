"""Conservative identity-first matching; incompatible variants veto equivalence."""
from dataclasses import dataclass
import re
import unicodedata

from rapidfuzz.fuzz import token_set_ratio

from pof.models import Product
from pof.product_evidence import title_model_code


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", text).lower()).strip()


def variants(p: Product) -> dict:
    result = {str(k).lower(): normalize(str(v)) for k, v in p.specs.items()}
    for unit in ("gb", "tb", "ml", "oz", "inch", "pack"):
        found = re.findall(r"\b(\d+(?:\.\d+)?)\s*" + unit + r"\b", p.title.lower())
        if found:
            result[unit] = "|".join(found)
    return result


@dataclass
class Match:
    kind: str
    confidence: float
    reason: str


def title_model_conflict(a: Product, b: Product) -> str:
    if a.model and b.model:
        return ""  # Structured models are handled by the established identifier rule.
    brand = a.brand or b.brand
    if not brand or not all(re.search(r"(?:^| )" + re.escape(normalize(brand)) + r"(?: |$)", normalize(p.title)) for p in (a, b)):
        return ""
    ac = a.model or title_model_code(a.title)
    bc = b.model or title_model_code(b.title)
    if ac and bc and normalize(ac) != normalize(bc):
        ap = re.sub(r"[0-9].*", "", ac.upper())
        bp = re.sub(r"[0-9].*", "", bc.upper())
        if ap and ap == bp:
            return f"Different model codes stated in listing titles: {ac} versus {bc}; confirm manufacturer models"
    return ""


def match(a: Product, b: Product) -> Match:
    av, bv = variants(a), variants(b)
    conflicts = [k for k in av.keys() & bv.keys() if av[k] != bv[k]]
    if conflicts or a.condition != b.condition:
        return Match("similar", 25, "Variant/condition conflict: " + ", ".join(conflicts or ["condition"]))
    if a.brand and b.brand and normalize(a.brand) != normalize(b.brand):
        return Match("similar", 30, "Different brands")
    model_conflict = title_model_conflict(a, b)
    if model_conflict:
        return Match("similar", 25, model_conflict)
    if a.gtin and b.gtin:
        if a.gtin == b.gtin:
            return Match("exact", 99, "Same GTIN; no known variant conflict")
        return Match("similar", 20, "Different GTINs")
    if a.model and b.model:
        if normalize(a.model) != normalize(b.model):
            return Match("similar", 30, "Different model numbers")
        if a.brand and b.brand:
            return Match("exact", 95, "Same brand and model; no known variant conflict")
    similarity = token_set_ratio(normalize(a.title), normalize(b.title))
    score = similarity * 0.65 + (15 if a.brand and a.brand.lower() == b.brand.lower() else 0)
    score += 15 if av and av == bv else 0
    # Fuzzy titles alone never establish equivalence.
    if score >= 85 and a.specs and b.specs and av and bv and a.brand and b.brand:
        return Match("equivalent", min(90, score), "Title, brand and specifications agree; review recommended")
    return Match("unverified", round(score, 2), "Insufficient identifiers/specifications")
