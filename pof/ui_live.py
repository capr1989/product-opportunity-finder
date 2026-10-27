"""Reusable guided live-research screens. Advanced data stays behind expanders."""
from dataclasses import asdict
import os
import time

import pandas as pd
import streamlit as st

from pof.exporting import csv_bytes, excel_bytes
from pof.finance import Assumptions
from pof.live.catalog import POLICIES, source_status
from pof.live.discovery import run_research
from pof.live.query import ResearchQuery
from pof.research import opportunities

MARKETS = {"USA": "US", "Panama": "PA", "USA and Panama": "US+PA"}
CATEGORIES = {"All categories": "", "Computers and tablets": "abcat0500000", "Headphones": "abcat0204000",
              "TVs": "abcat0101000", "Cell phones": "abcat0800000", "Appliances": "abcat0900000"}
METRIC_HELP = {
    "gross_margin": "Percentage of sale revenue remaining after product and direct acquisition costs, before other variable expenses.",
    "contribution_profit": "Estimated amount remaining after all modeled variable costs, including advertising.",
    "break_even_cpc": "Maximum estimated cost per ad click before a loss, using your assumed conversion rate.",
    "score": "A configurable research priority score, not a prediction of guaranteed sales.",
}


def navigate(page):
    st.session_state["next_workspace"] = page
    st.rerun()


def credentials():
    # Secrets live only in this browser session or the process environment; never in SQLite.
    values = {"BESTBUY_API_KEY": os.environ.get("BESTBUY_API_KEY", "")}
    values.update(st.session_state.get("source_credentials", {}))
    return values


def connection_rows(store):
    keys = credentials()
    rows = [source_status(name, config, store.get_config("collection_state", name) or {}, bool(keys["BESTBUY_API_KEY"]) if name == "Best Buy" else False)
            for name, config in store.configs("source").items()]
    priority = ["Best Buy", "CJdropshipping", "Amazon US", "AliExpress", "Walmart", "Target", "eBay US", "Alibaba"]
    return sorted(rows, key=lambda r: priority.index(r["Source"]) if r["Source"] in priority else len(priority))


def connect_sources(store):
    st.subheader("Live sources and access")
    st.write("Select a source to see its supported route, setup instructions and last collection result. No integration is called verified until it returns actual products.")
    rows = connection_rows(store)
    st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if k != "ready"} for r in rows]), hide_index=True, width="stretch")
    name = st.selectbox("Source connection", [r["Source"] for r in rows], key="connect_source")
    policy = POLICIES.get(name, {})
    config = store.get_config("source", name)
    enabled = st.toggle("Include this source in research", value=config.get("enabled", True), key="enable_" + name)
    if enabled != config.get("enabled", True):
        store.put_config("source", name, {**config, "enabled": enabled})
    st.info(policy.get("reason", "No reviewed live catalog integration is available yet. Authorized custom endpoints can be configured below."))
    st.write(policy.get("setup", "Use an authorized provider feed or configure a permitted public page in Advanced source configuration."))
    if policy.get("url"):
        st.link_button("Read provider access requirements", policy["url"])
    if name in {"Best Buy", "Amazon US", "AliExpress"}:
        if st.button("Test live connection", type="primary"):
            with st.spinner("Requesting up to three real catalog products…"):
                result = run_research(ResearchQuery(keywords="usb hub", limit=3, max_pages=1, available_only=False), [name], store, credentials())
            st.session_state["connection_test_run"] = result["run_id"]
        test_run = st.session_state.get("connection_test_run")
        test_summary = store.get_config("live_run", str(test_run)) if test_run else None
        if test_summary and any(r["source"] == name for r in test_summary.get("reports", [])):
            items = store.products(test_run, demo=False)
            if items:
                st.success(f"Retrieved {len(items)} actual products.")
                st.dataframe(pd.DataFrame([{"Product": p.title, "Listed price": p.price, "Currency": p.currency,
                    "Original listing": p.url} for p in items]), hide_index=True,
                    column_config={"Original listing": st.column_config.LinkColumn()})
                if st.button("Open tested research results"):
                    st.session_state["live_run_id"] = test_run
                    navigate("Research Results")
            else:
                st.warning(test_summary["reports"][0]["error"] or "No products were found. Broaden the search before treating the source as verified.")
    state = store.get_config("collection_state", name) or {}
    if state.get("last_error"):
        st.warning(state["last_error"])
        with st.expander("Connection diagnostics"):
            st.write("Last attempted:", state.get("last_attempt", "Never"))
            st.write("Issue:", state.get("error_code", "unknown"))
            technical = store.get_config("collection_diagnostic", name)
            if technical:
                st.write("Technical classification:", technical["exception_type"])
                st.write("Code locations:", ", ".join(technical["locations"]))
    if name == "Best Buy":
        from pof.live.bestbuy_browser import browser_installed
        if browser_installed():
            st.caption("Project Chromium installation detected.")
        else:
            st.info("For key-free browser collection, double-click InstallBrowser.cmd in the project folder once. It installs Playwright's official Chromium locally.")
        options = ["Public browser — no API key", "Official API — optional key"]
        current_mode = config.get("bestbuy_method", "api" if credentials()["BESTBUY_API_KEY"] else "browser")
        mode = st.radio("Best Buy collection method", options, index=1 if current_mode == "api" else 0)
        chosen_mode = "api" if mode == options[1] else "browser"
        if chosen_mode != current_mode:
            store.put_config("source", name, {**config, "bestbuy_method": chosen_mode})
        st.caption("Browser mode needs no key and stops at access barriers. The official API is optional.")
        with st.expander("Optional: connect Best Buy's official API", expanded=False):
            st.link_button("Get a Best Buy API key", "https://developer.bestbuy.com/")
            with st.form("bestbuy_credentials", clear_on_submit=True):
                value = st.text_input("Best Buy API key", type="password", help="Stored in this browser session only. Never paste it in chat.")
                if st.form_submit_button("Use key for this session"):
                    if not value.strip():
                        st.error("Enter a key or leave this optional connection skipped.")
                    else:
                        st.session_state["source_credentials"] = {"BESTBUY_API_KEY": value.strip()}
                        store.put_config("source", name, {**config, "bestbuy_method": "api"})
                        st.success("Key accepted for this session. It has not been verified yet. Run Test connection.")
            has_key = bool(credentials()["BESTBUY_API_KEY"])
            st.caption("Key present" if has_key else "No key configured")
            if st.button("Forget session key"):
                st.session_state.pop("source_credentials", None)
                st.rerun()
            if st.button("Test Best Buy connection", disabled=not has_key):
                with st.spinner("Requesting up to three actual products…"):
                    result = run_research(ResearchQuery(limit=3), ["Best Buy"], store, credentials())
                report = result["reports"][0]
                if report["error"]:
                    st.error(report["error"])
                elif result["products_found"]:
                    st.session_state["live_run_id"] = result["run_id"]
                    st.session_state["bestbuy_test_run_id"] = result["run_id"]
                    st.success(f"Verified: retrieved {result['products_found']} real products.")
                else:
                    st.warning("The request completed without products. The connector has not been verified with live products.")
            if st.session_state.get("bestbuy_test_run_id") and st.button("View connection test products"):
                st.session_state["live_run_id"] = st.session_state["bestbuy_test_run_id"]
                navigate("Research Results")


def setup_wizard(store):
    st.write("Set up live product research. Optional integrations can be skipped and connected later.")
    setup = store.get_config("settings", "onboarding") or {}
    step = st.session_state.get("setup_step", 1)
    labels = ["Target market", "Connect sources", "Cost assumptions", "First live search"]
    st.progress((step - 1) / 4, text=f"Step {step} of 4 — {labels[step - 1]}")
    if step == 1:
        market = st.radio("Where will you sell?", list(MARKETS), index=list(MARKETS.values()).index(setup.get("market", "US")))
        st.caption("A target market does not prove that a retailer ships there. Panama import/forwarding costs and eligibility must be confirmed.")
        if st.button("Save market and continue", type="primary"):
            store.put_config("settings", "onboarding", {**setup, "market": MARKETS[market]})
            st.session_state["setup_step"] = 2
            st.rerun()
    elif step == 2:
        connect_sources(store)
        if st.button("Continue — optional connections can be added later", type="primary"):
            st.session_state["setup_step"] = 3
            st.rerun()
    elif step == 3:
        saved = store.get_config("settings", "costs") or asdict(Assumptions())
        st.write("These costs are estimates you control. Expand Cost assumptions in the sidebar for every setting.")
        advertising = st.number_input("Estimated advertising cost per order ($)", 0.0, value=float(saved["advertising"]))
        fee = st.number_input("Marketplace fee (%)", 0.0, 100.0, float(saved["platform_rate"]) * 100)
        freight = st.number_input("Outbound shipping per order ($)", 0.0, value=float(saved["outbound_shipping"]))
        if st.button("Save costs and continue", type="primary"):
            store.put_config("settings", "costs", {**saved, "advertising": advertising, "platform_rate": fee / 100, "outbound_shipping": freight})
            for key in list(st.session_state):
                if key.startswith("cost_"):
                    del st.session_state[key]
            st.session_state["setup_step"] = 4
            st.rerun()
    else:
        ready = [r["Source"] for r in connection_rows(store) if r["ready"]]
        if ready:
            st.success("Connected sources: " + ", ".join(ready))
        else:
            st.info("No source is connected yet. You can finish setup and inspect source access, but real discovery needs a permitted source. Demo data will never be used instead.")
        if st.button("Finish setup and start research", type="primary"):
            store.put_config("settings", "onboarding", {**setup, "complete": True})
            navigate("New Research")
    if step > 1 and st.button("Previous setup step"):
        st.session_state["setup_step"] = step - 1
        st.rerun()
    if st.button("Skip setup for now"):
        store.put_config("settings", "onboarding", {**setup, "complete": True})
        navigate("Overview")


def new_research(store):
    st.subheader("1 · What are you looking for?")
    goal = st.radio("Research goal", ["Find profitable dropshipping products", "Discover retail deals", "Compare prices across stores",
        "Explore products by category", "Search for a specific product"], index=3)
    st.subheader("2 · Configure your search")
    rows = connection_rows(store)
    selected = st.multiselect("Sources", [r["Source"] for r in rows], default=[r["Source"] for r in rows if r["ready"]])
    for row in rows:
        if row["Source"] in selected and not row["ready"]:
            st.warning(f"{row['Source']}: {row['Collection method']} · {row['Verification']}. Open Source Manager for details.")
    cols = st.columns(2)
    keyword = cols[0].text_input("Keywords or product name (optional)")
    category = cols[1].selectbox("Category", list(CATEGORIES))
    st.caption("Some browser sources use category search hints rather than an exact category filter. Broad Amazon discovery defaults to Electronics.")
    cols = st.columns(2)
    minimum = cols[0].number_input("Minimum listed price", 0.0, value=0.0, help="In each source's displayed currency; no exchange-rate conversion is performed.")
    maximum = cols[1].number_input("Maximum listed price", 0.0, value=500.0, help="In each source's displayed currency. USD-only financial comparisons are separate.")
    with st.expander("Additional filters and collection limits"):
        brand = st.text_input("Brand (optional)")
        model = st.text_input("Model (optional)")
        seller = st.text_input("Seller or supplier (optional)")
        subcategory = st.text_input("Subcategory name (optional)")
        on_sale = st.checkbox("Advertised sale offers only", value=goal == "Discover retail deals")
        clearance = st.checkbox("Clearance offers only")
        available = st.checkbox("Available online only (exclude unknown availability)", value=False)
        limit = st.number_input("Maximum products per source", 1, 100, 25)
        pages = st.number_input("Maximum catalog pages per source", 1, 5, 3)
        margin = st.number_input("Minimum estimated contribution margin (%)", 0.0, 100.0, 0.0,
                                 help=METRIC_HELP["contribution_profit"])
        max_shipping = st.number_input("Maximum listed inbound shipping", 0.0, value=100.0,
            help="In the source's displayed currency. Missing shipping is handled by the unknown-values option below.")
        include_unknown = st.checkbox("Include products with unknown shipping/profitability", value=True)
        fresh = st.checkbox("Contact live sources again instead of using recent cache", value=True)
    st.subheader("3 · Run Research")
    st.caption("Collection uses the selected browser/API methods. Access challenges stop the source. New results open automatically; demonstration products are never substituted.")
    if st.button("Run Research", type="primary", disabled=not selected):
        try:
            market = (store.get_config("settings", "onboarding") or {}).get("market", "US")
            query = ResearchQuery(keywords=keyword.strip(), category_id=CATEGORIES[category], category_name=subcategory.strip(),
                brand=brand.strip(), model=model.strip(), seller=seller.strip(), minimum_price=minimum, maximum_price=maximum,
                on_sale=on_sale, clearance=clearance, available_only=available, target_market=market, limit=limit, max_pages=pages)
            progress = st.progress(0, text="Preparing research…")
            message = st.empty()
            started = time.monotonic()

            def update(fraction, label, count):
                progress.progress(fraction, text=label)
                message.caption(f"{count} products collected · {time.monotonic() - started:.1f} seconds elapsed")

            result = run_research(query, selected, store, credentials(), progress=update, refresh=fresh)
            store.put_config("live_run", str(result["run_id"]), {**result, "goal": goal, "minimum_margin": margin,
                "max_shipping": max_shipping, "include_unknown": include_unknown})
            st.session_state["live_run_id"] = result["run_id"]
            navigate("Research Results")
        except ValueError as exc:
            st.error(str(exc))


def results_dashboard(store, assumptions, weights):
    run_id = st.session_state.get("live_run_id")
    history = store.configs("live_run")
    if not run_id and history:
        run_id = max(map(int, history))
    if not run_id:
        st.info("No live research has been run yet. Choose sources and filters in New Research.")
        if st.button("Start New Research", type="primary"):
            navigate("New Research")
        return
    summary = store.get_config("live_run", str(run_id)) or {}
    products = store.products(run_id, demo=False)
    cols = st.columns(3)
    cols[0].metric("Products collected", len(products))
    cols[1].metric("Sources completed", sum(not r["error"] for r in summary.get("reports", [])))
    cols[2].metric("Elapsed seconds", summary.get("elapsed_seconds", 0))
    for report in summary.get("reports", []):
        if report["error"]:
            st.warning(f"{report['source']}: {report['error']}")
        else:
            st.caption(f"{report['source']} · {report['products']} products · {report['status']}")
    if not products:
        st.info("No live products were found. Try expanding the price range, removing filters, or selecting additional connected sources. Check Source Manager when a source reports an access issue.")
        if st.button("Open Source Manager"):
            navigate("Source Manager")
        if st.button("Adjust research"):
            navigate("New Research")
        return
    visible = [p for p in products if (p.shipping is not None and p.shipping <= summary.get("max_shipping", 100))
               or (p.shipping is None and summary.get("include_unknown", True))]
    st.subheader("Products found")
    st.caption("Prices are observations, not confirmed completed sales. Advertised discounts are not independently verified bargains. Availability and delivery must be confirmed before purchase.")
    records = [{"Product": p.title, "Source": p.source, "Listed price": p.price, "Currency": p.currency, "Price evidence": p.state("price"),
        "Quote type": "Advertised minimum — variant/coupon unconfirmed" if p.source_attributes.get("price_basis") == "advertised_minimum" else "Listed offer",
        "Availability": p.availability, "Brand": p.brand, "Category": p.category, "Listed shipping": p.shipping,
        "Collected (UTC)": p.collected_at, "Original listing": p.url} for p in visible]
    st.dataframe(pd.DataFrame(records), hide_index=True, width="stretch",
        column_config={"Original listing": st.column_config.LinkColumn("Original listing", display_text="View product"),
                       "Listed price": st.column_config.NumberColumn(format="%.2f")})
    if any(p.currency != "USD" for p in visible):
        st.info("Some sources returned a non-USD currency. Values are preserved, not converted; USD profitability is unavailable for those comparisons.")
    if any(p.source_attributes.get("price_basis") == "advertised_minimum" for p in visible):
        st.warning("Some supplier quotes are minimum/coupon offers. Confirm the variant and final unit cost before relying on them. They are excluded from automatic profit calculations.")
    if visible:
        index = st.selectbox("Inspect product", range(len(visible)), format_func=lambda i: visible[i].title)
        p = visible[index]
        st.write(f"**{p.title}**")
        st.link_button("Open original product listing", p.url)
        st.caption(f"{p.source} · collected {p.collected_at} · price: {p.state('price')}")
        if p.image_url and p.image_reuse_permitted and st.checkbox("Show provider-permitted product image"):
            # URL rendering is opt-in; browser handles permitted HTTPS image only.
            st.image(p.image_url, width=220)
        if st.button("Save product"):
            store.save(p)
            st.success("Saved to Saved Products")
        with st.expander("Evidence and technical details"):
            st.json({"record": p.record(), "field_status": {k: p.state(k) for k in p.record()}})
    st.subheader("Automatic comparisons")
    # Use the current run as the foundation, plus fresh real snapshots already collected from other sources.
    current_sources = {p.source for p in products}
    pool = visible[:]
    if st.checkbox("Also compare with previously collected, verified products", value=False):
        pool += [p for p in store.products(demo=False) if p.source not in current_sources and p.state("price") == "verified"]
    if len(pool) > 1000:
        st.warning("Comparison is limited to the first 1,000 products. Narrow the research for a complete comparison.")
    comparisons = opportunities(pool[:1000], assumptions, weights, store.reviews(), "dropshipping" in summary.get("goal", "").lower())
    comparisons = [r for r in comparisons if
        (r.get("contribution_margin") is not None and r["contribution_margin"] >= summary.get("minimum_margin", 0))
        or (r.get("contribution_margin") is None and summary.get("include_unknown", True))]
    if comparisons:
        fields = ["title", "source", "retailer", "match_kind", "match_confidence", "contribution_profit", "gross_margin", "break_even_cpc", "score", "profit_status"]
        st.dataframe(pd.DataFrame([{k: r.get(k) for k in fields} for r in comparisons]), hide_index=True,
            column_config={k: st.column_config.NumberColumn(help=v) for k, v in METRIC_HELP.items()})
        with st.expander("How were these calculations made?"):
            st.write("Observed purchase and retail prices are combined only for equivalent or manually approved matches. Inbound shipping and MOQ must be known. All fees, taxes, advertising and return allowances below are assumptions.")
            st.dataframe(pd.DataFrame([{"Assumption": k.replace('_', ' ').title(), "Value": v} for k, v in asdict(assumptions).items()]), hide_index=True)
    else:
        st.info("No defensible cross-source comparison is available yet. Collect equivalent products from a second authorized source. Missing supplier costs, shipping or product identity will not become invented profits.")
    st.download_button("Export these products (CSV)", csv_bytes([p.record() for p in visible]), "live-products.csv", "text/csv")
    st.download_button("Export research workbook", excel_bytes(visible, comparisons, asdict(assumptions)), "live-research.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Best Buy API content expires from the application within 72 hours. Downloaded copies and backups remain your responsibility under provider terms.")


HELP = {
    "Getting started": "Choose Setup in the sidebar. Set USA, Panama or both, review source access and cost assumptions, then start New Research. No source is automatically approved and no demo data is silently loaded.",
    "Connecting sources": "Open Source Manager. Each source lists collection method, credentials when needed, verification, last success and last error. Best Buy defaults to public browser mode without a key. Site terms may restrict automation; a configured adapter is not a verified working source.",
    "Running live research": "New Research → choose a goal → choose sources, category and optional keywords → Run Research. Leave keywords blank for catalog discovery. A restricted or unconnected source reports its failure; it never substitutes samples.",
    "Filters": "Price/category/brand filters are sent to supported catalogs. Further hard filters remove results; ranking weights reorder them. Choose whether to include unknown shipping or profitability. An unknown cost is not a zero cost. Only supported source filters can be executed server-side.",
    "Profitability": "Gross margin is (sale revenue minus landed acquisition cost) divided by sale revenue. Contribution profit also subtracts modeled variable expenses and advertising. Break-even CPC uses your conversion-rate assumption. Expand Cost assumptions in the sidebar to edit every cost.",
    "Opportunity scores": "Scores summarize weighted profitability, demand, competition, delivery, reliability, matching, freshness and uncertainty. Missing factors score zero. A high score is a research priority, not proof of future sales.",
    "Comparing suppliers": "Collect the same identifiers/model/variant from a supplier and retailer. Automatic matching checks GTIN, brand, model and known variants. Review uncertain matches in Product Comparison. No contribution estimate is shown without required costs.",
    "Saving and exporting": "Select a product in Research Results and click Save product. Export the current research there or use Export Center for the collected library. Exports include source links, collection times and assumptions. Provider-specific retention terms still apply to downloaded files.",
    "Troubleshooting": "Credential rejected: check Source Manager. Rate limit: wait before retrying. Access restricted: use a permitted source or obtain authorization. No products: broaden filters. Network failure: check connectivity. Demo data and genuine research are kept separate.",
    "API setup": "Best Buy: https://developer.bestbuy.com/ → Get API Key. Optional key entry is masked and stored for this browser session only; BESTBUY_API_KEY is also supported in the process environment. CJ and other APIs are evaluated but are not called implemented until a tested adapter exists.",
    "Browser setup": "Double-click InstallBrowser.cmd in the project folder. It installs Playwright's official Chromium into data/browsers without administrator privileges or global changes. Restart the app. Public browser mode uses no personal profile or stored login and stops at CAPTCHA/login/access barriers.",
    "Security": "Use a dedicated Windows VM and standard user, keep Defender and browser sandboxing enabled, keep credentials out of chat/CSV/Git, and use localhost only. The app does not bypass CAPTCHAs, access denials or anti-bot controls.",
}


def help_center():
    st.write("Practical help for live research and understanding its limits.")
    for title, content in HELP.items():
        with st.expander(title):
            st.write(content)
    with st.expander("Interactive tutorial — no API requests"):
        st.info("Tutorial only. The three steps below make no network requests and display no invented live products.")
        step = st.radio("Practice the workflow", ["1 · Choose a research goal", "2 · Set your filters", "3 · Review evidence"])
        if step.startswith("1"):
            st.selectbox("Practice goal", ["Explore categories", "Find retail deals"])
            st.caption("A broad goal does not need specific product names.")
        elif step.startswith("2"):
            st.slider("Practice maximum price", 10, 500, 100)
            st.caption("Price limits are hard filters. Unknown shipping can be included with a warning.")
        else:
            st.caption("Check the source link, observed price, collection time, missing costs and match confidence before relying on a comparison. For a fictional sample session, enable Demo dataset explicitly in the sidebar.")
