"""Beginner discovery screens; old research tools remain accessible separately."""
from dataclasses import asdict

import streamlit as st

from pof.finance import Assumptions
from pof.opportunity_engine import (DiscoverySettings, TAXONOMY, available_sources, build_leads,
                                    run_session, session_products)
from pof.storage import Store
from pof.ui_live import credentials, navigate


def safe_listing(product, key):
    # Product validation rejects non-HTTP schemes; do not render untrusted Markdown.
    if product.url.startswith("https://"):
        st.link_button("Open original listing · " + product.source, product.url, key=key)


def opportunity_cards(store, session, assumptions):
    products = {Store.identity(p): p for p in session_products(store, session)}
    settings = DiscoverySettings(**session["settings"])
    # Re-evaluate references at render time: expired content cannot live on in derived cards.
    leads = build_leads(list(products.values()), settings, assumptions, store.reviews())
    decisions = store.configs("opportunity_decision")
    st.subheader("Products worth investigating")
    st.caption("A listing price is evidence of an asking price, not proof of sales. Potential leads are not profit estimates.")
    states = st.multiselect("Show findings", ["Potential Lead", "Financially Evaluated", "Rejected / Unattractive"],
                            default=["Potential Lead", "Financially Evaluated"])
    show_dismissed = st.checkbox("Show not interested findings")
    selected = []
    visible = [r for r in leads if r["state"] in states and
               (show_dismissed or decisions.get(r["id"], {}).get("decision") != "not interested")]
    st.caption(f"{len(products)} unique product observations · {len(leads)} findings · showing {min(30, len(visible))} cards. Analysis is capped at 300 unique products and 100 ranked findings per session.")
    for row in visible[:30]:
        a, b = products[row["buy_id"]], products.get(row["sell_id"])
        with st.container(border=True):
            st.subheader(a.title)
            st.write(row["state"])
            if a.image_url and a.image_reuse_permitted and (store.get_config("settings", "application") or {}).get("show_images", False):
                st.image(a.image_url, width=160)
            cols = st.columns(3)
            cols[0].metric("Observed purchase quote", f"{a.currency} {a.price:,.2f}" if a.price is not None else "Unknown")
            cols[1].metric("Retail asking price", f"{b.currency} {b.price:,.2f}" if b and b.price is not None else "Not found")
            financial = row["financial"]
            cols[2].metric("Estimated contribution / unit", f"USD {financial['contribution_profit']:,.2f}" if financial["known"] else "Not established")
            st.write(row["promise"])
            if row["observed_gap"] is not None:
                st.caption(f"Observed listing difference: {row['currency']} {row['observed_gap']:,.2f}. Costs have not been deducted from this difference.")
            st.text(f"Buy: {a.source} · {a.role} · observed {a.collected_at}")
            if b:
                st.text(f"Selling reference: {b.source} · observed {b.collected_at}")
            if row["missing"]:
                st.warning("Still needed: " + "; ".join(row["missing"]))
            if row["reasons"]:
                st.warning("; ".join(row["reasons"]))
            st.write("Next step: " + row["next_step"])
            st.caption("Demand: " + row["demand"])
            key = session["id"] + row["id"]
            safe_listing(a, "buy_" + key)
            if b:
                safe_listing(b, "sell_" + key)
            if st.checkbox("Select for Deep Research", key="select_" + key):
                selected.append(a)
            actions = st.columns(3)
            if actions[0].button("Investigate further", key="deep_" + key):
                st.session_state["deep_seed_ids"] = [Store.identity(a)]
                st.session_state["deep_seed_run_ids"] = session["run_ids"]
                st.session_state["next_discovery_mode"] = "Deep Research"
                st.rerun()
            if actions[1].button("Save opportunity", key="save_" + key):
                store.save(a)
                store.put_config("opportunity_decision", row["id"], {"decision": "saved", "session": session["id"]})
                st.success("Saved for follow-up research")
            if actions[2].button("Not interested", key="dismiss_" + key):
                store.put_config("opportunity_decision", row["id"], {"decision": "not interested", "session": session["id"]})
                st.rerun()
            with st.expander("Compare sources and match evidence"):
                st.write(row.get("match_reason", "No comparable listing found"))
                st.caption(f"Validated match confidence: {row['match_confidence']} / 100. Candidate title similarity is separate from equivalence.")
                st.json({"purchase_specifications": a.specs, "retail_specifications": b.specs if b else {},
                         "purchase_price_basis": a.source_attributes.get("price_basis", "Not reported"),
                         "shipping": a.shipping, "MOQ": a.moq, "delivery_days": a.delivery_days,
                         "destination": a.target_country, "stock": a.availability})
                if b:
                    review = st.selectbox("Your match decision", ["automatic", "approve", "reject"], key="review_" + key)
                    st.caption("Approval is your judgment; it cannot fill missing prices, shipping, MOQ or currency.")
                    if st.button("Record match decision", key="record_" + key):
                        store.review(row["id"], review, "Reviewed in discovery cards")
                        st.rerun()
            with st.expander("View profit breakdown"):
                if financial["known"]:
                    st.json(financial)
                    st.caption("Scenario fees, advertising, tax, returns and fulfillment are assumptions. A retail asking price does not guarantee a sale.")
                    st.json(row["assumptions"])
                else:
                    st.write("Profit is unresolved. Verify the missing evidence before using the financial scenario in Advanced Tools.")
    if not visible:
        st.info("No findings in this view. Check source failures, include rejected findings, or run another category scan. No sample products were substituted.")
    if selected and st.button("Deep Research selected candidates", type="primary"):
        st.session_state["deep_seed_ids"] = [Store.identity(p) for p in selected]
        st.session_state["deep_seed_run_ids"] = session["run_ids"]
        st.session_state["next_discovery_mode"] = "Deep Research"
        st.rerun()
    saved = [p for p in store.products(demo=False) if Store.identity(p) in store.saved()][:100]
    if saved:
        with st.expander("Investigate saved products"):
            chosen = st.multiselect("Saved candidates", [Store.identity(p) for p in saved],
                                    format_func=lambda x: next(p.title for p in saved if Store.identity(p) == x))
            if chosen and st.button("Use saved candidates for Deep Research"):
                st.session_state["deep_seed_ids"] = chosen
                st.session_state["deep_seed_run_ids"] = []
                st.session_state["next_discovery_mode"] = "Deep Research"
                st.rerun()


def discovery_home(store, *, guided=False):
    from pof.settings import get_settings
    defaults = get_settings(store)
    st.title("Find Products Worth Selling")
    st.write("Explore real catalogs, compare possible sourcing options, and see what still needs checking.")
    if "next_discovery_mode" in st.session_state:
        st.session_state["discovery_mode"] = st.session_state.pop("next_discovery_mode")
    if "discovery_mode" not in st.session_state:
        st.session_state["discovery_mode"] = defaults["default_mode"]
    mode = st.radio("Research depth", ["Quick Scan", "Deep Research"], horizontal=True, key="discovery_mode")
    st.caption("Quick Scan explores several categories. Deep Research searches for comparable offers and checks the evidence for selected products.")
    if store.history() and st.button("Review collected products"):
        navigate("Product Review Center")
    if not guided:
        cols = st.columns(2)
        if cols[0].button("Guided Research"):
            navigate("Guided Research")
        if cols[1].button("Advanced Tools"):
            navigate("Advanced Tools")
    model, market, budget, desired, categories, delivery = "Explore All", "US", 500.0, 5.0, [], None
    with st.expander("Your selling plans" if guided else "Optional preferences", expanded=guided):
        models = ["Explore All", "Dropshipping", "Retail Reselling", "Wholesale"]
        model = st.selectbox("Business model", models, index=models.index(defaults["business_model"]))
        market = st.selectbox("Selling market", ["US", "PA", "US+PA"], index=["US", "PA", "US+PA"].index(defaults["market"]), format_func=lambda x: {"US": "USA", "PA": "Panama", "US+PA": "Both"}[x])
        budget = st.number_input("Available investment (USD)", 0.0, 1_000_000.0, float(defaults["budget"]))
        desired = st.number_input("Desired contribution per unit (USD)", 0.0, 1_000_000.0, float(defaults["minimum_profit"]))
        allowed = [c for c in TAXONOMY if c not in defaults["excluded_categories"]]
        categories = st.multiselect("Categories of interest", allowed, default=[c for c in defaults["categories"] if c in allowed])
        days = st.number_input("Preferred maximum delivery days (0 = no preference)", 0, 365, 0)
        delivery = days or None
    with st.expander("Scan limits"):
        query_limit = st.slider("Searches across categories / follow-up candidates", 1, 12, defaults["quick_queries"] if mode == "Quick Scan" else defaults["deep_queries"])
        source_limit = st.slider("Maximum sources per search", 1, 5, defaults["source_limit"])
        product_limit = st.slider("Products per source per search", 1, 20, defaults["products_per_source"])
        st.caption("Collection stops at these limits. Use Streamlit's Stop control to interrupt; completed collection steps are saved and can be resumed.")
    settings = DiscoverySettings(mode, model, market, budget, desired, tuple(categories or allowed),
                                 query_limit, source_limit, product_limit, delivery, defaults["minimum_margin"])
    names = available_sources(store, credentials(), settings)
    st.caption("Automatically selected: " + (", ".join(names) or "No available live sources. Review Source Manager."))
    st.caption(f"At most {query_limit * len(names)} source requests; {query_limit * len(names) * product_limit} product observations before deduplication. Each adapter also has its own request limits.")
    seeds = []
    if mode == "Deep Research":
        ids = set(st.session_state.get("deep_seed_ids", []))
        seeds = [p for p in store.products(demo=False) if Store.identity(p) in ids]
        if seeds:
            st.info(f"Investigating {len(seeds)} selected products, up to the configured search limit.")
        else:
            st.caption("No candidates selected: discover candidates across categories first, then investigate findings below.")
    assumptions = Assumptions(**(store.get_config("settings", "costs") or asdict(Assumptions())))
    if st.button("Run " + mode, type="primary", disabled=not names):
        bar = st.progress(0.0, text="Preparing research")
        session = run_session(store, settings, credentials(), seeds=seeds,
                              assumptions=assumptions, progress=lambda fraction, text: bar.progress(fraction, text=text))
        st.session_state["discovery_session_id"] = session["id"]
        bar.progress(1.0, text="Research complete")
    sessions = store.configs("discovery_session")
    if sessions:
        ids = sorted(sessions, key=lambda x: sessions[x]["created"], reverse=True)
        selected_id = st.selectbox("Research sessions", ids,
            index=ids.index(st.session_state.get("discovery_session_id")) if st.session_state.get("discovery_session_id") in ids else 0,
            format_func=lambda x: f"{sessions[x]['settings']['mode']} · {sessions[x]['created']} · {sessions[x]['status']}")
        session = sessions[selected_id]
        failures = {r["source"] + ": " + r["error"] for r in session["reports"] if r.get("error")}
        for failure in sorted(failures):
            st.warning(failure)
        if session["status"] in {"paused", "running"} and st.button("Resume research"):
            bar = st.progress(0.0)
            session = run_session(store, settings, credentials(), session_id=selected_id,
                                  progress=lambda fraction, text: bar.progress(fraction, text=text))
            st.rerun()
        with st.expander("Search plan and collection report"):
            st.json(session["plan"])
            for report in session["reports"]:
                if report.get("error"):
                    st.warning(report["source"] + ": " + report["error"])
                else:
                    st.write(report)
                    if report.get("products") and report.get("priced_products") == 0:
                        st.warning(report["source"] + " returned product identities but no readable prices. Economics remain unknown.")
        opportunity_cards(store, session, Assumptions(**session["assumptions"]))
    else:
        st.info("Ready to explore live products. No keywords or CSV files are required.")
