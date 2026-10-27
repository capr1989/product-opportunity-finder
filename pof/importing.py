"""Bounded CSV ingestion: strings stay strings; no dynamic code or file paths."""
import csv
from dataclasses import fields
import io
import json

from pof.models import NUMERIC, Product

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000


def import_csv(raw: bytes, force_demo: bool = False) -> list[Product]:
    if len(raw) > MAX_BYTES:
        raise ValueError("CSV exceeds 10 MiB")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    allowed = {f.name for f in fields(Product)}
    if not reader.fieldnames or not {"source", "title"}.issubset(reader.fieldnames):
        raise ValueError("CSV requires source and title columns")
    if set(reader.fieldnames) - allowed:
        raise ValueError("Unknown columns: " + ", ".join(set(reader.fieldnames) - allowed))
    output = []
    for index, row in enumerate(reader, 2):
        if index > MAX_ROWS + 1:
            raise ValueError("CSV exceeds 10,000 rows")
        try:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("column count mismatch")
            clean = {k: v for k, v in row.items() if v.strip()}
            for key in clean:
                if key in NUMERIC or key == "retention_hours":
                    clean[key] = float(clean[key])
                elif key in {"demo", "fragile", "restricted", "image_reuse_permitted"}:
                    if clean[key].lower() not in {"true", "false"}:
                        raise ValueError(f"{key} must be true or false")
                    clean[key] = clean[key].lower() == "true"
                elif key in {"specs", "states", "demand_reference", "source_attributes"}:
                    clean[key] = json.loads(clean[key])
            clean["demo"] = force_demo or clean.get("demo", False)
            output.append(Product(**clean))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid CSV row {index}: {exc}") from None
    return output
