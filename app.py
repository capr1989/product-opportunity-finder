"""Local Streamlit dashboard. Run with Launch.cmd or the documented localhost command."""
from dataclasses import asdict
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd
import streamlit as st

from pof.connectors import collect, status
from pof.demo import demo_products
from pof.demand import diagnostics, import_keywords, keyword_ideas
from pof.exporting import csv_bytes, excel_bytes
from pof.filters import evaluate
from pof.finance import Assumptions, calculate
from pof.importing import import_csv
from pof.models import NUMERIC
from pof.research import deals, opportunities, search
from pof.scoring import DEFAULT_WEIGHTS
from pof.storage import Store

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Product Opportunity Finder", page_icon="🔎", layout="wide")


@st.cache_resource
def initialize():
    (ROOT / "logs").mkdir(exist_ok=True)
    logger = logging.getLogger("pof")
    if not logger.handlers:
        handler = RotatingFileHandler(ROOT / "logs" / "events.log", maxBytes=1_000_000, backupCount=3)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    # Do not enable HTTP/Google debug logging: it can expose OAuth metadata.
    logging.getLogger("google.ads.googleads.client").setLevel(logging.CRITICAL)
    return Store(ROOT / "data" / "research.sqlite3")


store = initialize()
PAGES = ["Overview", "Product Search", "Broad Discovery", "Retail Deal Hunter", "Dropshipping Opportunities",
         "Product Comparison", "Google Ads Keyword Research", "Saved Products", "Research History",
         "Source Manager", "API Settings and Diagnostics", "Export Center"]
st.sidebar.title("🔎 Opportunity Finder")
page = st.sidebar.radio("Workspace", PAGES)
demo = st.sidebar.toggle("Demo dataset", value=False, help="Fictional data stays separate from real research")
if demo:
    st.warning("DEMO MODE · All displayed products and metrics are fictional. No live evidence or sales predictions.")
    if st.sidebar.button("Load / reset demo snapshots"):
        store.add_run("DEMO fixtures", demo_products())
        st.rerun()

with st.sidebar.expander("Cost assumptions", expanded=False):
    saved_assumptions = store.get_config("settings", "costs") or asdict(Assumptions())
    inputs = {}
    for key, default in saved_assumptions.items():
        inputs[key] = st.number_input(key.replace("_", " ").title(), min_value=0.0,
            max_value=1.0 if key.endswith("rate") else 100000.0, value=float(default),
            step=0.01 if key.endswith("rate") else 0.1, format="%.4f", key=f"cost_{key}")
    assumptions = Assumptions(**inputs)
    st.caption("Rates are fractions: 0.15 = 15%. Shipping in imports is per unit. Taxes are nonrecoverable landed taxes.")
    if st.button("Save cost defaults"):
        store.put_config("settings", "costs", inputs)
        st.success("Saved")
with st.sidebar.expander("Ranking preferences"):
    stored_weights = store.get_config("settings", "weights") or DEFAULT_WEIGHTS
    weights = {key: st.number_input(key.title(), 0, 100, int(value), key=f"weight_{key}")
               for key, value in stored_weights.items()}
    st.caption("Preferences affect score; hard filters exclude rows. Missing factors receive zero points.")
    if st.button("Save ranking defaults"):
        store.put_config("settings", "weights", weights)

sources = store.configs("source")
products = store.products(demo=demo)
products = [p for p in products if p.demo or sources.get(p.source, {}).get("enabled", True)]
keyword_rows = (store.get_config("keywords", "latest") or {}).get("rows", [])
mappings = store.configs("keyword_map")
for product in products:
    mapping = mappings.get(store.identity(product))
    if mapping:
        row = next((r for r in keyword_rows if r["keyword"] == mapping["keyword"]), None)
        if row:
            product.demand_reference = row.copy()
            for key in ("monthly_searches", "competition_index", "competition", "cpc", "low_bid", "high_bid", "trend", "seasonality"):
                if key in row:
                    setattr(product, key, row[key])
                    product.states[key] = row["status"]
            product.demand_confidence = "manual keyword association"


def table(rows, key="table"):
    if not rows:
        st.info("No results yet. Load the demo, import a CSV, or configure an authorized source.")
        return
    clean = [{k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()
              if k not in {"source_record", "retail_record", "assumptions", "breakdown"}} for row in rows]
    st.dataframe(pd.DataFrame(clean), width="stretch", hide_index=True, key=key,
                 column_config={k: st.column_config.LinkColumn(k) for k in
                                ("url", "retail_url", "reference_url")})


TEXT_FILTERS = ["title", "category", "subcategory", "brand", "condition", "availability", "supplier_country",
                "target_country", "trend", "competition", "seasonality", "demand_confidence", "currency",
                "match_kind", "profit_status"]
BOOL_FILTERS = ["fragile", "restricted", "known"]
NUMBER_FILTERS = sorted(NUMERIC | {"supplier_cost", "selling_price", "gross_profit", "contribution_profit",
    "gross_margin", "contribution_margin", "roi", "advertising", "match_confidence", "score", "verified_discount"})


def filtering(rows, context):
    st.subheader("Hard filters")
    presets = store.configs("preset")
    selected = st.selectbox("Saved preset", ["Custom / default", *presets], key=f"preset_{context}")
    if st.button("Apply selected preset", key=f"apply_{context}") and selected in presets:
        st.session_state[f"loaded_{context}"] = presets[selected]
        # Clear only this filter builder's widget state before rerendering.
        for key in list(st.session_state):
            if key.startswith(f"f_{context}_"):
                del st.session_state[key]
        st.rerun()
    if st.button("Reset filters", key=f"reset_{context}"):
        st.session_state.pop(f"loaded_{context}", None)
        for key in list(st.session_state):
            if key.startswith(f"f_{context}_"):
                del st.session_state[key]
        st.rerun()
    loaded = st.session_state.get(f"loaded_{context}", {"logic": "AND", "rules": []})
    top = st.selectbox("Combine groups", ["AND", "OR"], index=["AND", "OR"].index(loaded.get("logic", "AND")),
                       key=f"f_{context}_top")
    groups = []
    with st.expander("Build filter groups (AND / OR)", expanded=bool(loaded.get("rules"))):
        for group_index in range(2):
            default_group = loaded.get("rules", [])[group_index] if len(loaded.get("rules", [])) > group_index else {}
            prefix = f"f_{context}_{group_index}"
            st.markdown(f"**Group {group_index + 1}**")
            logic = st.selectbox("Group logic", ["AND", "OR"],
                index=["AND", "OR"].index(default_group.get("logic", "AND")), key=prefix + "logic")
            defaults = default_group.get("rules", [])
            count = st.number_input("Number of rules", 0, 15, len(defaults), key=prefix + "count")
            rules = []
            for index in range(count):
                base = prefix + f"_{index}"
                default = defaults[index] if index < len(defaults) else {}
                columns = st.columns([2, 1, 2, 1])
                fields = TEXT_FILTERS + NUMBER_FILTERS + BOOL_FILTERS
                field = columns[0].selectbox("Metric", fields,
                    index=fields.index(default.get("field", "price")), key=base + "field")
                operators = ["gte", "lte", "eq", "ne"] if field in NUMBER_FILTERS else ["eq", "ne", "contains", "not_contains"]
                op = columns[1].selectbox("Operator", operators,
                    index=operators.index(default.get("op", operators[0])) if default.get("op", operators[0]) in operators else 0,
                    key=base + "op")
                if field in NUMBER_FILTERS:
                    value = columns[2].number_input("Value", value=float(default.get("value", 0))
                        if isinstance(default.get("value", 0), (int, float)) else 0.0, key=base + "value_n")
                elif field in BOOL_FILTERS:
                    value = columns[2].selectbox("Value", [True, False], key=base + "value_b")
                else:
                    value = columns[2].text_input("Value", str(default.get("value", "")), key=base + "value_s")
                unknown = columns[3].selectbox("Unknowns", ["exclude", "include"],
                    index=1 if default.get("unknown") == "include" else 0, key=base + "unknown")
                rules.append({"field": field, "op": op, "value": value, "unknown": unknown})
            if rules:
                groups.append({"logic": logic, "rules": rules})
    group = {"logic": top, "rules": groups}
    name = st.text_input("Preset name", key=f"name_{context}")
    if st.button("Save filter preset", key=f"save_{context}") and name.strip():
        store.put_config("preset", name.strip(), group)
        st.success("Preset saved")
    result = []
    for row in rows:
        passed, warnings = evaluate(row, group)
        if passed:
            result.append({**row, "filter_warnings": "; ".join(warnings)})
    st.caption(f"{len(result):,} of {len(rows):,} rows pass. Use ne / not_contains for exclusions; unknown values have an explicit policy.")
    return result


def product_details(items):
    if not items:
        return
    index = st.selectbox("Inspect / save product", range(len(items)),
                         format_func=lambda i: f"{items[i].source} · {items[i].title}")
    p = items[index]
    st.json({"record": p.record(), "field_status": {k: p.state(k) for k in p.record()}})
    if st.button("Save selected product"):
        store.save(p)
        st.success("Saved")
    history = store.price_history(p)
    if history:
        st.line_chart(pd.DataFrame(history).set_index("collected_at")[["price"]])


def opportunity_view(items, dropship=False):
    try:
        rows = opportunities(items, assumptions, weights, store.reviews(), dropship)
    except ValueError as exc:
        st.warning(str(exc))
        return []
    rows = filtering(rows, "dropship" if dropship else "comparison")
    table(rows)
    st.caption("Sale prices are observed asking prices, not evidence of completed sales. Profit is a scenario estimate.")
    if rows:
        index = st.selectbox("Inspect opportunity", range(len(rows)),
            format_func=lambda i: f"{rows[i]['title']} → {rows[i]['retailer']} · {rows[i]['score']:.1f}")
        row = rows[index]
        st.json({"match": {k: row[k] for k in ("match_kind", "match_confidence", "match_reason", "review")},
                 "score_breakdown": row["breakdown"], "financial_assumptions": row["assumptions"],
                 "profit_status": row["profit_status"]})
        decision = st.selectbox("Manual equivalence decision", ["automatic", "approve", "reject"])
        note = st.text_input("Review evidence / variant checks")
        if st.button("Save match review"):
            store.review(row["pair"], decision, note)
            st.rerun()
        if st.button("Save opportunity's purchase product"):
            p = next(p for p in items if store.identity(p) == store.identity(type(items[0])(**row["source_record"])))
            store.save(p)
            st.success("Saved")
    return rows


st.title(page)
st.caption("Local research workspace · USD economics · Evidence and assumptions stay visible")

if page == "Overview":
    cols = st.columns(4)
    cols[0].metric("Products", len(products))
    cols[1].metric("Sources", len({p.source for p in products}))
    cols[2].metric("Research runs", len(store.history()))
    cols[3].metric("Saved products", len(store.saved()))
    st.subheader("Start researching")
    st.write("Use Source Manager to import a dataset or collect from an authorized endpoint. Enable Demo dataset in the sidebar to explore fictional examples. All data stays in local SQLite.")
    if products:
        table([p.record() for p in products[:100]])
    else:
        st.info("Your research library is empty. No sample data has been loaded automatically.")
    st.caption("Opportunity scores organize research priorities. They do not predict actual sales.")

elif page in {"Product Search", "Broad Discovery"}:
    query = st.text_input("Product, model, GTIN, brand or keywords" if page == "Product Search" else "Optional discovery keywords")
    categories = sorted({p.category for p in products if p.category})
    selected_categories = st.multiselect("Categories", categories)
    selected_sources = st.multiselect("Sources", sorted({p.source for p in products}))
    subset = search(products, query)
    subset = [p for p in subset if (not selected_categories or p.category in selected_categories)
              and (not selected_sources or p.source in selected_sources)]
    rows = filtering([p.record() for p in subset], page)
    table(rows)
    if st.button("Save research session"):
        store.add_run(f"{page}: {query or ', '.join(selected_categories) or 'all'}", subset)
        st.success("Session snapshot saved")
    st.caption("Search and discovery use the collected library. Configure and collect enabled sources in Source Manager to refresh it.")
    product_details(subset)

elif page == "Retail Deal Hunter":
    st.write("Deals compare current verified prices from different merchants for exact matches. Advertised original prices are not used as evidence.")
    rows = filtering(deals(products), "deals")
    table(rows)
    st.download_button("Download deals CSV", csv_bytes(rows), "retail-deals.csv", "text/csv")

elif page in {"Dropshipping Opportunities", "Product Comparison"}:
    query = st.text_input("Narrow products before comparison")
    subset = search(products, query)
    opportunity_view(subset, page == "Dropshipping Opportunities")
    with st.expander("Independent financial calculator"):
        cost = st.number_input("Unit cost", 0.0, value=10.0)
        sale = st.number_input("Expected sale price", 0.0, value=30.0)
        shipping = st.number_input("Inbound shipping per unit", 0.0, value=2.0)
        quantity = st.number_input("MOQ", 1, value=1)
        st.json(calculate(cost, sale, shipping, quantity, assumptions))

elif page == "Source Manager":
    st.subheader("Source access and configuration")
    table([{"source": name, "role": s["role"], "kind": s["kind"], "status": status(s)} for name, s in sources.items()])
    name = st.selectbox("Edit source", ["Add new source", *sources])
    current = sources.get(name, {})
    with st.form("source_form"):
        source_name = st.text_input("Source name", current.get("name", ""))
        role = st.selectbox("Role", ["supplier", "retailer"], index=0 if current.get("role") == "supplier" else 1)
        kinds = ["import", "csv", "json", "public_page", "browser"]
        kind = st.selectbox("Connector", kinds, index=kinds.index(current.get("kind", "import")))
        url = st.text_input("Authorized HTTPS endpoint / single product page", current.get("url", ""))
        host = st.text_input("Exact allowed hostname (no scheme or path)", current.get("allowed_host", ""))
        enabled = st.checkbox("Enabled", current.get("enabled", True))
        permission = st.checkbox("I have verified that this endpoint permits this automated access", current.get("permission_confirmed", False))
        interval = st.number_input("Minimum request interval (seconds)", 0.5, 60.0, float(current.get("interval", 2)))
        cache = st.number_input("Cache duration (seconds)", 0, 604800, int(current.get("cache_seconds", 3600)))
        st.caption("JSON/CSV endpoints must supply normalized records. Browser mode requires an explicitly installed Chromium and only parses static structured data; JavaScript is disabled.")
        if st.form_submit_button("Save source"):
            if not source_name.strip() or len(source_name) > 100:
                st.error("Provide a source name of 1–100 characters")
            elif url and ("?" in url or "#" in url):
                st.error("Keep tokens and query credentials out of source URLs; use an authorized credential-free feed or import")
            else:
                store.put_config("source", source_name.strip(), {"name": source_name.strip(), "role": role,
                    "kind": kind, "url": url.strip(), "allowed_host": host.strip().lower(), "enabled": enabled,
                    "permission_confirmed": permission, "interval": interval, "cache_seconds": cache})
                st.rerun()
    st.subheader("Collect from configured sources")
    choices = [name for name, s in sources.items() if status(s).startswith("configured")]
    chosen = st.multiselect("Sources to collect (bounded endpoints only)", choices)
    refresh = st.checkbox("Refresh cached endpoints")
    if st.button("Collect selected sources", disabled=not chosen):
        progress = st.progress(0)
        collected = []
        for index, name in enumerate(chosen):
            try:
                with st.spinner(f"Collecting {name}…"):
                    result, cached = collect(sources[name], store, refresh)
                collected.extend(result)
                st.success(f"{name}: {len(result)} records ({'cache' if cached else 'live endpoint'})")
            except Exception as exc:
                st.error(f"{name}: {str(exc) if isinstance(exc, ValueError) else 'Collection failed; check configuration, network and browser installation'}")
            progress.progress((index + 1) / len(chosen))
        if collected:
            store.add_run("Authorized source collection", collected)
            st.success("Collection saved. Open a research screen to analyze it.")
    st.subheader("Import product CSV")
    st.download_button("Download demo CSV / column template", csv_bytes([p.record() for p in demo_products()]),
                       "product-template.csv", "text/csv")
    upload = st.file_uploader("UTF-8 product CSV (10 MiB / 10,000 rows)", type=["csv"])
    label = st.text_input("Import/session label", "Product import")
    if st.button("Validate and import", disabled=upload is None):
        try:
            imported = import_csv(upload.getvalue(), force_demo=demo)
            store.add_run(label, imported)
            st.success(f"Imported {len(imported)} records. CSV claims are estimated unless states explicitly identifies verified fields.")
        except (ValueError, UnicodeError, TypeError):
            st.error("Invalid CSV. Check column names, numeric values, timestamps, and JSON specs/states. Nothing was imported.")

elif page == "Google Ads Keyword Research":
    st.write("Read-only keyword ideas and historical metrics. This application cannot create campaigns or spend ad money.")
    text = st.text_area("Keyword seeds, one per line (up to 20)")
    if products:
        suggested = st.multiselect("Discover keywords from product titles/categories", sorted({p.title for p in products} | {p.category for p in products if p.category}))
    else:
        suggested = []
    cols = st.columns(2)
    country = cols[0].text_input("Google geo criterion ID (US = 2840)", "2840")
    language = cols[1].text_input("Google language criterion ID (English = 1000)", "1000")
    interval = st.number_input("Google minimum request interval (seconds)", 0.5, 60.0, 2.0)
    cache_duration = st.number_input("Keyword cache seconds", 0, 604800, 86400)
    if st.button("Request Google keyword ideas"):
        try:
            with st.spinner("Requesting one bounded page of keyword ideas…"):
                rows, cached = keyword_ideas(store, list(dict.fromkeys([k.strip() for k in text.splitlines() if k.strip()] + suggested)),
                    country, language, interval, cache_duration)
            store.put_config("keywords", "latest", {"rows": rows})
            store.put_config("diagnostic", "google", {"result": "Successful keyword planning request", "cached": cached})
            st.success(f"{len(rows)} keywords received ({'cache' if cached else 'Google Ads API'}). Bids use the account currency.")
            st.rerun()
        except Exception as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Google client initialization failed; verify environment OAuth configuration"
            store.put_config("diagnostic", "google", {"result": message})
            st.error(message)
    upload = st.file_uploader("Keyword CSV alternative", type=["csv"])
    st.caption("Required: keyword,monthly_searches. Optional: competition_index,competition,cpc,low_bid,high_bid,trend,seasonality,bid_currency. Imported metrics are estimated.")
    if st.button("Import keyword data", disabled=upload is None):
        try:
            rows = import_keywords(upload.getvalue())
            store.put_config("keywords", "latest", {"rows": rows})
            st.rerun()
        except (ValueError, TypeError, UnicodeError):
            st.error("Invalid keyword CSV; no data imported")
    table(keyword_rows)
    if keyword_rows and products:
        st.subheader("Associate a keyword with a product")
        st.caption("This is a research association, not evidence of product sales. CPC is never inferred from bid ranges.")
        index = st.selectbox("Product", range(len(products)), format_func=lambda i: products[i].title)
        keyword = st.selectbox("Keyword", [r["keyword"] for r in keyword_rows])
        if st.button("Save keyword association"):
            store.put_config("keyword_map", store.identity(products[index]), {"keyword": keyword})
            st.success("Association saved")

elif page == "Saved Products":
    saved = [p for p in products if store.identity(p) in store.saved()]
    table([p.record() for p in saved])
    product_details(saved)

elif page == "Research History":
    history = store.history()
    table([dict(zip(["id", "session", "created", "products"], row)) for row in history])
    if history:
        run = st.selectbox("Inspect run", [r[0] for r in history])
        table([p.record() for p in store.products(run, demo=demo)], "history_products")
        other = st.selectbox("Compare against run", [r[0] for r in history], index=min(1, len(history) - 1))
        before = {store.identity(p): p for p in store.products(other, demo=demo)}
        changes = []
        for p in store.products(run, demo=demo):
            previous = before.get(store.identity(p))
            changes.append({"title": p.title, "source": p.source, "new_product": previous is None,
                "previous_price": previous.price if previous else None, "current_price": p.price,
                "price_change": p.price - previous.price if previous and p.price is not None and previous.price is not None else None})
        table(changes, "changes")

elif page == "API Settings and Diagnostics":
    st.json(diagnostics())
    st.json(store.get_config("diagnostic", "google") or {"last_request": "No live request attempted"})
    st.write("Credentials are read from process environment only. No secrets are shown or saved through this dashboard. Restart after rotation. See docs/GOOGLE_ADS.md.")
    st.json({"database": "SQLite initialized", "migrations": [1], "source_count": len(sources),
             "UI_default": "127.0.0.1:8501", "browser": "optional; explicit Chromium installation required",
             "data_storage": "data/", "logs": "rotating structured safe-event logs"})

elif page == "Export Center":
    st.write("Exports include source snapshots, assumptions, missing data, match confidence and score breakdowns. Values are estimates unless explicitly verified.")
    export_query = st.text_input("Limit export products by keyword")
    export_products = search(products, export_query)
    try:
        rows = opportunities(export_products, assumptions, weights, store.reviews())
        st.download_button("Export products CSV", csv_bytes([p.record() for p in export_products]), "products.csv", "text/csv")
        st.download_button("Export opportunities CSV", csv_bytes(rows), "opportunities.csv", "text/csv")
        st.download_button("Export full research workbook", excel_bytes(export_products, rows, asdict(assumptions), keyword_rows),
            "research.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ValueError as exc:
        st.warning(str(exc))
