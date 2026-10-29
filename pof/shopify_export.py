"""Local-only Shopify CSV and research workbook; no publishing or credentials."""
import csv
import html
import io
import math
import re

from openpyxl import Workbook

from pof.exporting import flatten
from pof.security import spreadsheet_safe

# Verified against Shopify's official current template on 2026-10-29.
HEADERS = ("Title", "URL handle", "Description", "Vendor", "Type", "Tags", "Published on online store",
           "Status", "SKU", "Option1 name", "Option1 value", "Option2 name", "Option2 value", "Option3 name", "Option3 value", "Price", "Cost per item",
           "Product image URL", "Image alt text")


def shopify_export(items, prices, *, exclude_incomplete=True, status="draft", store_currency="USD"):
    if status not in {"draft", "active"}:
        raise ValueError("Unsupported export status")
    if store_currency not in {"USD", "PAB"}:
        raise ValueError("Unsupported store currency; no currency conversion is performed")
    rows, reports = [], []
    for item in items:
        p, cid = item["product"], item["id"]
        warnings = []
        price = prices.get(cid)
        valid_price = isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(price) and price > 0
        if not valid_price:
            warnings.append("An explicit positive selling price in your Shopify store currency is required")
        if p.price is None or p.source_attributes.get("price_basis") == "advertised_minimum":
            warnings.append("Selected-variant unit cost is unverified")
        if p.currency != store_currency:
            warnings.append("Source quote currency differs from store currency; cost omitted, no conversion assumed")
        if p.shipping is None or p.moq is None:
            warnings.append("Shipping or minimum quantity is unverified")
        if not p.image_url or not p.image_reuse_permitted:
            warnings.append("No image with confirmed reuse permission; image omitted")
        if p.source_attributes.get("direct_fulfillment") is not True:
            warnings.append("Fulfillment eligibility requires manual review")
        if not p.specs or p.state("specs") != "verified":
            warnings.append("Variant/specification details require manual review")
        included = valid_price and not (exclude_incomplete and warnings) and not p.demo
        reports.append({"candidate": cid, "title": p.title, "included": included, "warnings": warnings})
        if not included:
            continue
        description = ""
        if p.state("specs") == "verified":
            # Generate only from short factual specifications, never copied prose.
            facts = [(k, v) for k, v in p.specs.items() if k.lower() in
                     {"material", "color", "size", "dimensions", "capacity", "weight", "pack"}]
            description = "<ul>" + "".join(f"<li>{html.escape(str(k))}: {html.escape(str(v))}</li>" for k, v in facts) + "</ul>" if facts else ""
        handle = re.sub(r"[^a-z0-9]+", "-", p.title.lower()).strip("-")[:60] or "product"
        row = {"Title": p.title, "URL handle": handle + "-" + cid[:12], "Description": description,
               "Vendor": p.brand if p.state("brand") == "verified" else "", "Type": p.category,
               "Tags": "research-review", "Published on online store": "false", "Status": status,
               "SKU": p.sku or "POF-" + cid[:12], "Option1 name": "Title", "Option1 value": "Default Title",
               "Price": f"{price:.2f}", "Cost per item": "", "Product image URL": p.image_url if p.image_reuse_permitted else "",
               "Image alt text": p.title if p.image_reuse_permitted and p.image_url else ""}
        if p.state("specs") == "verified":
            options = [(k, str(v)) for k, v in p.specs.items() if k.lower() in {"color", "size", "pack"} and len(str(v)) <= 200]
            for index, (name, value) in enumerate(options[:3], 1):
                row[f"Option{index} name"] = name.title()
                row[f"Option{index} value"] = value
        for index in (2, 3):
            row.setdefault(f"Option{index} name", "")
            row.setdefault(f"Option{index} value", "")
        # Currency is not a per-row Shopify CSV field. Never convert supplier costs.
        if p.price is not None and p.currency == store_currency and p.state("price") == "verified" and p.source_attributes.get("price_basis") != "advertised_minimum":
            row["Cost per item"] = f"{p.price:.2f}"
        sanitized = {k: spreadsheet_safe(v) for k, v in row.items()}
        changed = [k for k in row if sanitized[k] != row[k]]
        if changed:
            warnings.append("Spreadsheet-dangerous text escaped; review fields: " + ", ".join(changed))
        rows.append(sanitized)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig"), rows, reports


def research_workbook(items, evidence, assumptions, histories):
    workbook = Workbook()
    workbook.remove(workbook.active)
    datasets = {
        "Products and ratings": [{**i["product"].record(), "candidate_id": i["id"], "personal_rating": i["rating"], "personal_notes": i["note"]} for i in items],
        "Comparisons and economics": [{"candidate_id": i["id"], **evidence.get(i["id"], {})} for i in items],
        "Financial assumptions": [assumptions],
        "Price observations": [{"candidate_id": cid, **row} for cid, rows in histories.items() for row in rows],
        "Sources and evidence": [{"candidate_id": i["id"], "url": i["product"].url, "timestamp": i["product"].collected_at, "field_states": i["product"].states} for i in items],
    }
    for name, rows in datasets.items():
        sheet = workbook.create_sheet(name)
        # References become records only in this explicit user export.
        normalized = []
        for row in rows:
            row = dict(row)
            if "references" in row:
                row["references"] = [p.record() for p in row["references"]]
            normalized.append(flatten(row))
        headers = list(dict.fromkeys(k for row in normalized for k in row))
        sheet.append(headers or ["No data"])
        for row in normalized:
            sheet.append([row.get(k) for k in headers])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
