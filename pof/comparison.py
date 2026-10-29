"""Plain-language explanations over existing match and financial evidence."""
from pof.matching import match, normalize, variants, title_model_conflict
from pof.product_evidence import clean_specs, title_model_code


UNKNOWN = "Missing / not reported"


def amount(value, currency):
    return f"{currency} {value:,.2f}" if value is not None else UNKNOWN


def comparison_summary(a, b, row):
    if b is None:
        return {"status": "Uncertain", "facts": [], "support": [], "conflicts": [],
                "missing": ["An independent retail comparison is missing"],
                "why_comparable": "No independent comparable listing has been found yet.",
                "next_step": "Investigate additional retail offers for this exact product."}
    m = match(a, b)
    av, bv = variants(a), variants(b)
    facts, support, conflicts, missing = [], [], [], []
    for label, key in (("Brand", "brand"), ("Reported model", "model"), ("UPC / EAN / GTIN", "gtin")):
        left, right = getattr(a, key), getattr(b, key)
        if not left or not right:
            result = "Not confirmed on both listings"
            missing.append(label + " is missing from " + ("both listings" if not left and not right else "purchase listing" if not left else "retail listing"))
        elif normalize(left) == normalize(right):
            result = "Reported values agree"
            support.append(label + ": " + left)
        else:
            result = "Reported values differ"
            conflicts.append(label + ": " + left + " versus " + right)
        facts.append({"Attribute": label, "Purchase": left or UNKNOWN, "Retail": right or UNKNOWN,
                      "Evidence": result + f"; purchase {a.state(key)}, retail {b.state(key)}"})
    facts.append({"Attribute": "Source listing ID", "Purchase": a.sku or UNKNOWN, "Retail": b.sku or UNKNOWN,
                  "Evidence": "Source-specific IDs (e.g. ASIN vs Best Buy SKU) are not shared product identifiers"})
    if a.condition != "unknown" and b.condition != "unknown" and a.condition != b.condition:
        conflicts.append("Condition: " + a.condition + " versus " + b.condition)
    facts.append({"Attribute": "Condition", "Purchase": a.condition, "Retail": b.condition,
                  "Evidence": "Unconfirmed" if "unknown" in {a.condition, b.condition} else "Agrees" if a.condition == b.condition else "Conflict"})
    purchase_specs, retail_specs = clean_specs(a.specs), clean_specs(b.specs)
    for key in sorted(purchase_specs.keys() | retail_specs.keys()):
        left, right = purchase_specs.get(key, ""), retail_specs.get(key, "")
        agrees = bool(left and right and normalize(left) == normalize(right))
        facts.append({"Attribute": str(key), "Purchase": left or UNKNOWN, "Retail": right or UNKNOWN,
                      "Evidence": "Reported specification agrees" if agrees else "Reported values differ" if left and right else "Missing on one side"})
        if agrees:
            support.append(str(key) + ": " + left)
    for key in sorted(av.keys() & bv.keys()):
        if av[key] != bv[key]:
            conflicts.append(f"Variant/specification {key}: {av[key]} versus {bv[key]}")
    if not purchase_specs:
        missing.append("Detailed purchase specifications were not collected")
    if not retail_specs:
        missing.append("Detailed retail specifications were not collected")
    ac, bc = title_model_code(a.title), title_model_code(b.title)
    if ac or bc:
        facts.append({"Attribute": "Model code visible in title (unverified clue)", "Purchase": ac or UNKNOWN,
                      "Retail": bc or UNKNOWN, "Evidence": "Title text only; never establishes equivalence"})
    model_conflict = title_model_conflict(a, b)
    if model_conflict:
        conflicts.append(model_conflict)
    for key in sorted((av.keys() | bv.keys()) - (a.specs.keys() | b.specs.keys())):
        facts.append({"Attribute": "Title clue: " + key, "Purchase": av.get(key, UNKNOWN),
                      "Retail": bv.get(key, UNKNOWN), "Evidence": "Extracted from title; selected variant not verified"})
    common = sorted((set(normalize(a.title).split()) & set(normalize(b.title).split())) -
                    {"the", "and", "with", "for", "a", "an", "of", "to"})[:12]
    why = "Candidate search/title similarity" + (f" ({row['similarity']:g}/100)" if "similarity" in row else "")
    why += "; shared title terms: " + ", ".join(common) if common else "; review source identity evidence below"
    why += ". Similar wording is not proof of equivalence."
    status = "Contradicted" if conflicts else "Verified by matching evidence" if m.kind in {"exact", "equivalent"} else "Uncertain"
    if conflicts:
        next_step = "Verify the exact product model and selected variant on both listings; resolve the reported conflict first."
    elif m.kind not in {"exact", "equivalent"} and row.get("review") != "approve":
        next_step = "Verify the exact product model or a shared UPC/GTIN on both listings."
    elif a.source_attributes.get("price_basis") == "advertised_minimum":
        next_step = "Confirm the selected supplier variant and final unit price without coupon/minimum-price conditions."
    elif a.shipping is None:
        next_step = "Confirm inbound shipping for the purchase listing to " + (a.target_country or "your selling market") + "."
    elif a.availability != "in_stock":
        next_step = "Check purchase availability and fulfillment to your selling market."
    elif a.moq is None:
        next_step = "Confirm the minimum order quantity and package quantity."
    else:
        next_step = row.get("next_step", "Investigate additional retail offers and review all cost assumptions.")
    return {"status": status, "facts": facts, "support": support, "conflicts": list(dict.fromkeys(conflicts)),
            "missing": missing, "why_comparable": why, "match_reason": m.reason, "next_step": next_step}


PHRASES = {
    "Confirm product identity, variant, material and package quantity": "product equivalence is not confirmed",
    "Confirm inbound shipping per unit": "inbound shipping is unknown",
    "Refresh stale shipping costs": "inbound shipping costs are stale",
    "Confirm minimum order quantity": "minimum order quantity is unknown",
    "Refresh stale minimum order quantity": "minimum order quantity is stale",
    "Obtain comparable USD quotes; no currency conversion is assumed": "comparable USD quotes are unavailable (no conversion assumed)",
    "Confirm both current unit prices": "one or both unit prices are missing",
    "Confirm product condition": "product condition is unconfirmed",
    "Confirm stock and fulfillment availability": "stock or fulfillment availability is unconfirmed",
    "Confirm selected variant cost without minimum/coupon conditions": "the selected-variant unit cost is unconfirmed",
    "Refresh stale prices": "one or both prices are stale",
    "Confirm single-unit direct fulfillment": "single-unit direct fulfillment is unconfirmed",
    "Confirm supplier direct fulfillment to the customer": "supplier direct fulfillment is unconfirmed",
    "Confirm Panama delivery and import charges": "Panama delivery and import charges are unconfirmed",
    "Confirm delivery within your preferred time": "delivery within your preferred time is unconfirmed",
    "Find a comparable independent retail listing": "an independent selling-price reference is missing",
    "Verify variant, shipping and fulfillment": "variant, shipping and fulfillment remain unconfirmed",
}


def profit_explanation(row, summary):
    if row["financial"].get("known"):
        return "Contribution is an estimate using the displayed quotes and financial assumptions; the retail asking price does not guarantee a sale."
    blockers = [PHRASES.get(item, "required evidence is missing: " + item) for item in row.get("missing", [])]
    if summary["conflicts"]:
        blockers.insert(0, "the reported product identities or variants conflict")
    if row.get("reasons") and not summary["conflicts"]:
        blockers.extend(row["reasons"])
    return "Profit cannot be calculated because " + "; ".join(dict.fromkeys(blockers or ["required financial inputs are unconfirmed"])) + ". Unknown costs are not zero, and a listing price gap is not profit."
