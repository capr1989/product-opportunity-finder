"""Bounded explicit catalog attributes and clearly separated title clues."""
import math
import re


def scalar(value):
    if isinstance(value, str):
        return value.strip()[:400]
    if type(value) in {int, float} and math.isfinite(value):
        return str(value)
    if isinstance(value, dict) and "value" in value:
        amount = scalar(value["value"]) if not isinstance(value["value"], (dict, list)) else ""
        unit = value.get("unitText") or value.get("unitCode") or ""
        return (amount + (" " + unit if isinstance(unit, str) and unit else "")).strip()[:400]
    return ""


def clean_specs(value):
    if isinstance(value, dict):
        pairs = list(value.items())[:32]
    elif isinstance(value, list):
        pairs = [(p.get("name"), p.get("value")) for p in value[:32] if isinstance(p, dict)]
    else:
        return {}
    aliases = {"package quantity": "pack", "pack quantity": "pack", "number of items": "pack",
               "product dimensions": "dimensions", "colour": "color"}
    result = {}
    for name, raw in pairs:
        if not isinstance(name, str) or not name.strip():
            continue
        key = aliases.get(name.strip().lower(), name.strip().lower())[:80]
        text = scalar(raw)
        if text:
            result[key] = text
    return result


def explicit_fields(record):
    """Preserve only fields actually present; never infer brand/model from a name."""
    specs = {}
    for field in ("specs", "specifications", "additionalProperty", "details"):
        for key, value in clean_specs(record.get(field)).items():
            if key not in specs and len(specs) < 32:
                specs[key] = value
    for key in ("color", "size", "material", "dimensions", "width", "height", "depth", "weight"):
        text = scalar(record.get(key))
        if text:
            specs[key] = text
    brand = record.get("brand") or record.get("brandName") or record.get("manufacturer") or ""
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    model = record.get("model") or record.get("modelNumber")
    if isinstance(model, dict):
        model = model.get("name", "")
    return {"brand": scalar(brand), "model": scalar(model),
            "gtin": scalar(record.get("gtin14") or record.get("gtin13") or record.get("gtin12") or record.get("gtin8")
                           or record.get("gtin") or record.get("upc") or record.get("ean")), "specs": specs}


def catalog_labels(text):
    """Read explicit labels, not arbitrary prose or possible variant option lists."""
    names = {"brand", "model", "model number", "upc", "gtin", "color", "colour", "size", "material",
             "dimensions", "package quantity", "pack quantity", "number of items"}
    record, specs = {}, {}
    lines = text.splitlines()[:160]
    for index, line in enumerate(lines):
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = label.strip().lower()
        if label not in names:
            continue
        value = value.strip()
        if not value and index + 1 < len(lines) and ":" not in lines[index + 1]:
            value = lines[index + 1].strip()
        value = re.split(r"\s+(?:SKU|UPC|Model|Brand):", value, flags=re.I)[0].strip()[:400]
        if not value:
            continue
        if label in {"brand", "model", "model number", "upc", "gtin"}:
            record["model" if label == "model number" else label] = value
        else:
            specs[label] = value
    record["specs"] = clean_specs(specs)
    return explicit_fields(record)


def title_model_code(title):
    # Clues only. These never populate authoritative model fields or grant equivalence.
    prefix = re.split(r"\b(?:for|fits|compatible with|replacement for)\b", title, maxsplit=1, flags=re.I)[0]
    codes = {m.group(0).upper() for m in re.finditer(r"\b([A-Z]{1,3})\d{3,5}[A-Z]?\b", prefix, re.I)
             if m.group(1).upper() not in {"HD", "UHD", "FHD", "DPI", "RPM", "MHZ", "GHZ", "USB", "IPX", "GB", "TB"}}
    return next(iter(codes)) if len(codes) == 1 else ""
