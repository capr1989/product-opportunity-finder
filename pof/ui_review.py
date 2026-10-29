"""Movie-style personal review, evidence cards and local export wizard."""
from dataclasses import asdict, replace
from datetime import date
import hashlib

import pandas as pd
import streamlit as st

from pof.finance import Assumptions, calculate
from pof.review_analysis import evidence, monthly_scenario
from pof.review_store import RATINGS, ReviewStore
from pof.shopify_export import research_workbook, shopify_export


def money(value, currency="USD"):
    return f"{currency} {value:,.2f}" if value is not None else "Unknown"


def decision_card(item, proof, store, *, scenarios=True, controls=None):
    p, cid = item["product"], item["id"]
    financial = proof.get("financial", {"known": False})
    st.subheader(p.title)
    st.caption(f"{p.source} · {p.category or 'Category unknown'} · {p.collected_at} · Personal rating: {item['rating']}")
    if p.image_url and p.image_reuse_permitted and (store.get_config("settings", "application") or {}).get("show_images", False):
        st.image(p.image_url, width=220)
    cols = st.columns(3)
    cols[0].metric("Observed unit quote", money(p.price, p.currency))
    cols[1].metric("Estimated contribution / unit", money(financial.get("contribution_profit")))
    cols[2].metric("Upfront inventory estimate", money(financial.get("inventory_commitment")))
    if controls:
        controls()
    best = proof.get("best")
    if best and best["observed_gap"] is not None:
        st.write("Observed listing difference: " + money(best["observed_gap"], best["currency"]) + ". This is not profit.")
    if not financial.get("known"):
        st.warning("Profitability is unverified. " + "; ".join(proof.get("missing", [])))
    if best and best.get("reasons"):
        st.warning("Investigation concerns: " + "; ".join(best["reasons"]))
    st.write("Why investigate: " + (best["promise"] if best else "A catalog candidate that needs independent retail and cost evidence."))
    st.caption("Main risks: different variants, unavailable fulfillment, changing quotes, returns and advertising costs. An asking price does not establish demand or a sale.")
    st.write("Next step: " + (best["next_step"] if best else "Confirm selected variant, destination, shipping and an independent selling reference."))
    st.link_button("Open source listing", p.url, key="listing_" + cid, disabled=not bool(p.url))
    with st.expander("Sourcing, specifications and comparable offers"):
        st.write(f"Brand: {p.brand or 'Unknown'} · Model: {p.model or 'Unknown'} · Condition: {p.condition}")
        st.write(f"Source role: {p.role}. Retailers are not confirmed dropshipping suppliers.")
        st.write(f"Shipping per unit: {money(p.shipping, p.currency)} · Minimum quantity: {p.moq if p.moq is not None else 'Unknown'}")
        st.write(f"Delivery days: {p.delivery_days if p.delivery_days is not None else 'Unknown'} · Stock: {p.availability}")
        st.write(f"Supplier ratings: {p.rating if p.rating is not None else 'Unknown'} / 5 · Reviews: {p.reviews if p.reviews is not None else 'Unknown'}")
        st.caption("Seller ratings are a limited reliability signal, not a fulfillment guarantee.")
        if p.specs:
            st.table(pd.DataFrame([{"Specification": str(k), "Reported value": str(v), "Evidence": p.state("specs")} for k, v in p.specs.items()]))
        refs = proof.get("references", [])
        quoted = [r.price for r in refs if r.price is not None and r.currency == "USD"]
        if quoted:
            st.write("Observed USD retail-price range: " + money(min(quoted)) + " to " + money(max(quoted)))
        for index, ref in enumerate(refs[:10]):
            st.link_button(f"{ref.source} · {money(ref.price, ref.currency)} · {ref.title[:70]}", ref.url,
                           key=f"ref_{cid}_{index}", disabled=not bool(ref.url))
            st.caption("Observed " + ref.collected_at)
        if best:
            st.write(f"Match confidence: {best['match_confidence']} / 100 · {best['match_kind']}")
            st.write(best["match_reason"])
        demand = p.demand_reference
        st.write("Keyword evidence: " + (str(p.monthly_searches) + " monthly searches (" + p.state("monthly_searches") + ")" if p.monthly_searches is not None else "Unknown"))
        if demand:
            st.table(pd.DataFrame([{"Keyword evidence": k.replace("_", " "), "Reported value": str(v)} for k, v in demand.items() if k in {"keyword", "monthly_searches", "competition", "low_bid", "high_bid", "collected_at", "trend", "bid_currency"}]))
        st.caption("Searches, trend indicators and ad bids are research signals, not product sales or measured acquisition costs.")
    if scenarios:
        with st.expander("Monthly revenue and profit scenarios"):
            st.warning("Hypothetical scenarios only. Monthly units are your assumptions, not sales forecasts.")
            reference = financial.get("selling_price")
            if reference is None and p.role == "retailer" and p.currency == "USD":
                reference = p.price
            saved_scenario = store.get_config("review_scenario", cid) or {}
            price = st.number_input("Selling-price scenario (USD)", 0.0, 1_000_000.0, float(saved_scenario.get("selling_price", reference or 0)), key="scenario_price_" + cid)
            units = st.slider("Base monthly unit-sales assumption", 0, 10000, int(saved_scenario.get("units", 100)), key="units_" + cid)
            ads = st.number_input("Advertising cost per order (USD)", 0.0, 100000.0, float(saved_scenario.get("advertising", (best or {}).get("assumptions", {}).get("advertising", 5))), key="ads_" + cid)
            modeled = financial
            if financial.get("known"):
                assumptions = Assumptions(**best["assumptions"])
                modeled = calculate(p.price, price, p.shipping, p.moq, replace(assumptions, advertising=ads))
            contribution = modeled.get("contribution_profit") if modeled.get("known") else None
            results = []
            for label, default in (("Conservative", units // 2), ("Base", units), ("Optimistic", min(10000, units * 2))):
                if saved_scenario.get("units") == units:
                    default = saved_scenario.get("unit_scenarios", {}).get(label, default)
                amount = st.number_input(label + " monthly units", 0, 10000, default, key="qty_" + label + cid + str(units))
                results.append({"Scenario": label, "Units (assumed)": amount,
                                **monthly_scenario(price, contribution, amount)})
            st.table(pd.DataFrame(results))
            st.caption("Revenue = assumed selling price × assumed units. Monthly contribution = estimated unit contribution × assumed units. Fixed overhead is excluded. Unknown profit remains unknown.")
            if st.button("Save scenario", key="save_scenario_" + cid):
                store.put_config("review_scenario", cid, {"selling_price": price, "advertising": ads, "units": units,
                                                          "unit_scenarios": {r["Scenario"]: r["Units (assumed)"] for r in results}})
                st.success("Scenario saved separately from observed quotes")
    with st.expander("Profit breakdown, formulas and observation history"):
        if financial.get("known"):
            st.table(pd.DataFrame([{"Component": key.replace("_", " "), "Estimated value": value}
                                   for key, value in financial.items() if key != "known"]))
            st.caption("Landed cost = quote + inbound shipping + duties + nonrecoverable taxes. Contribution subtracts payment/platform fees, return allowance, advertising, outbound shipping and other modeled costs.")
        else:
            st.write("No defensible contribution estimate is available. Missing costs are not zero.")
        history = ReviewStore(store).history(cid)
        st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")


def review_center(store, favorites=False, watchlist=False):
    from pof.review_shortcuts import FOCUS_GUARD
    # First-party constant only: never interpolate external/user data into HTML.
    st.html(FOCUS_GUARD, unsafe_allow_javascript=True)
    review = ReviewStore(store)
    st.title("My Favorites" if favorites else "Maybe Later" if watchlist else "Product Review Center")
    st.caption("Your ratings are personal preferences, separate from opportunity scores and match confidence.")
    runs = store.history()
    sessions = store.configs("discovery_session")
    with st.expander("Find products and filter scans", expanded=False):
        selected_sessions = st.multiselect("Research sessions", sorted(sessions, key=lambda sid: sessions[sid]["created"], reverse=True),
            format_func=lambda sid: f"{sessions[sid]['settings']['mode']} · {sessions[sid]['settings']['business_model']} · {sessions[sid]['created']}")
        selected_runs = st.multiselect("Historical scans (empty = all scans)", [r[0] for r in runs],
                                      format_func=lambda rid: next(f"{r[1]} · {r[2]}" for r in runs if r[0] == rid))
        search = st.text_input("Search products")
        status = st.selectbox("Review status", ["All", "Unreviewed", "Reviewed"])
        ratings = st.multiselect("Personal ratings", list(RATINGS))
        source = st.multiselect("Product sources", sorted(store.configs("source")))
        model = st.selectbox("Business model filter", ["All", "Explore All", "Dropshipping", "Retail Reselling", "Wholesale", "Legacy / manual"])
        since = st.date_input("Collected on or after", date(2000, 1, 1))
        confidence = st.slider("Minimum comparison confidence", 0, 100, 0)
        profitability = st.selectbox("Profitability", ["All", "Unverified", "Positive modeled contribution", "Nonpositive modeled contribution"])
        include_pass = st.checkbox("Include products rated Pass")
    selected_runs = list(set(selected_runs) | {rid for sid in selected_sessions for rid in sessions[sid]["run_ids"]})
    items = review.items(selected_runs, favorites=favorites, watchlist=watchlist)
    unavailable = review.unavailable_preferences(favorites=favorites, watchlist=watchlist)
    if unavailable:
        with st.expander("Saved preferences with unavailable listing evidence"):
            st.caption("Personal ratings and notes remain saved. Licensed or unavailable product observations cannot be shown; matching recollected evidence can restore the product card.")
            st.dataframe(pd.DataFrame(unavailable), hide_index=True)
    if model != "All":
        sessions = store.configs("discovery_session").values()
        model_runs = {rid for s in sessions if s["settings"]["business_model"] == model for rid in s["run_ids"]}
        known_runs = {rid for s in store.configs("discovery_session").values() for rid in s["run_ids"]}
        items = [i for i in items if (i["run_id"] not in known_runs if model == "Legacy / manual" else i["run_id"] in model_runs)]
    items = [i for i in items if (not source or i["product"].source in source) and
             search.casefold() in (i["product"].title + " " + i["product"].brand + " " + i["product"].model).casefold()
             and date.fromisoformat(i["product"].collected_at[:10]) >= since]
    total = len(items)
    reviewed = sum(i["rating"] != "Unrated" for i in items)
    st.progress(reviewed / max(total, 1), text=f"{reviewed} of {total} products reviewed")
    items = [i for i in items if (include_pass or i["rating"] != "Pass") and (not ratings or i["rating"] in ratings)
             and (status == "All" or (i["rating"] == "Unrated") == (status == "Unreviewed"))]
    assumptions = Assumptions(**(store.get_config("settings", "costs") or asdict(Assumptions())))
    from pof.opportunity_engine import DiscoverySettings
    context = DiscoverySettings(**sessions[selected_sessions[0]]["settings"]) if len(selected_sessions) == 1 else None
    proofs = evidence(items[:100], store, assumptions, context)
    items = [i for i in items if proofs.get(i["id"], {}).get("confidence", 0) >= confidence and
             (profitability == "All" or
              (profitability == "Unverified" and not proofs.get(i["id"], {}).get("financial", {}).get("known")) or
              (profitability == "Positive modeled contribution" and proofs.get(i["id"], {}).get("financial", {}).get("contribution_profit", -1) > 0) or
              (profitability == "Nonpositive modeled contribution" and proofs.get(i["id"], {}).get("financial", {}).get("known") and proofs[i["id"]]["financial"]["contribution_profit"] <= 0))]
    if not items:
        st.info("No products in this view. Run a scan, change filters, or rate products Love it / Like to fill Favorites.")
        return
    sorting = st.selectbox("Sort products", ["Most recent", "Rating", "Estimated profit", "Margin", "Confidence", "Category"])
    if sorting == "Rating":
        items.sort(key=lambda i: {"Love it": 0, "Like": 1, "Maybe later": 2, "Unrated": 3, "Pass": 4}[i["rating"]])
    elif sorting == "Category":
        items.sort(key=lambda i: i["product"].category)
    elif sorting in {"Estimated profit", "Margin", "Confidence"}:
        key = {"Estimated profit": "contribution_profit", "Margin": "contribution_margin", "Confidence": "confidence"}[sorting]
        items.sort(key=lambda i: (proofs.get(i["id"], {}).get("confidence") if key == "confidence" else
                                 proofs.get(i["id"], {}).get("financial", {}).get(key)) or -float("inf"), reverse=True)
    view = st.radio("Review view", ["Review Mode", "Overview Mode"], horizontal=True)
    st.caption("Overview comparison calculations cover up to 100 products at a time; narrow scans/filters for larger libraries. Each opened card is investigated separately.")
    if view == "Overview Mode":
        grouping = st.selectbox("Group overview by", ["None", "Scan", "Personal rating"])
        overview = pd.DataFrame([{"Product": i["product"].title, "Source": i["product"].source,
            "Scan": i["run_id"], "Personal rating": i["rating"], "Category": i["product"].category,
            "Last quote": i["product"].price, "Currency": i["product"].currency,
            "Estimated profit": proofs.get(i["id"], {}).get("financial", {}).get("contribution_profit"),
            "Estimated margin (%)": proofs.get(i["id"], {}).get("financial", {}).get("contribution_margin"),
            "Estimated inventory cash": proofs.get(i["id"], {}).get("financial", {}).get("inventory_commitment"),
            "Match confidence": proofs.get(i["id"], {}).get("confidence", 0),
            "Missing evidence": "; ".join(proofs.get(i["id"], {}).get("missing", [])),
            "Observed": i["product"].collected_at} for i in items])
        if grouping != "None":
            overview = overview.sort_values(grouping, kind="stable")
        st.dataframe(overview, hide_index=True, width="stretch")
    queue_key = hashlib.sha256(str([selected_sessions, selected_runs, search, source, model, ratings, status, favorites, watchlist]).encode()).hexdigest()
    saved = store.get_config("review_cursor", queue_key) or {}
    index = next((n for n, i in enumerate(items) if i["id"] == saved.get("candidate_id")), min(saved.get("index", 0), len(items) - 1))
    if view == "Overview Mode":
        cid = st.selectbox("Open product for review", [i["id"] for i in items], format_func=lambda x: next(i["product"].title for i in items if i["id"] == x))
        index = next(n for n, i in enumerate(items) if i["id"] == cid)
    item = items[index]
    def move(step):
        target = max(0, min(index + step, len(items) - 1))
        store.put_config("review_cursor", queue_key, {"candidate_id": items[target]["id"], "index": target})
        st.rerun()
    nav = st.columns(4)
    if nav[0].button("Previous", disabled=index == 0):
        move(-1)
    if nav[1].button("Next", disabled=index == len(items) - 1):
        move(1)
    if nav[2].button("Skip"):
        move(1)
    if nav[3].button("Resume Review"):
        move(0)
    st.caption(f"Product {index + 1} of {len(items)} in this review queue")
    def controls():
        note_key = "note_" + item["id"]
        note = st.session_state.get(note_key, item["note"])
        shortcuts = st.checkbox("Enable rating shortcuts (Ctrl+Shift+1–4)")
        cols = st.columns(5)
        for n, rating in enumerate(RATINGS[1:] + ("Unrated",)):
            if cols[n].button(rating, key="rate_" + rating, shortcut=f"Ctrl+Shift+{n+1}" if shortcuts and n < 4 else None):
                review.rate(item["id"], rating, note)
                store.put_config("review_cursor", queue_key, {"index": index})
                st.rerun()
        with st.expander("My notes", expanded=bool(item["note"])):
            note = st.text_area("Personal notes", item["note"], max_chars=10000, key=note_key)
            if st.button("Save personal notes"):
                review.rate(item["id"], item["rating"], note)
                st.success("Notes saved")
    decision_card(item, proofs.get(item["id"]) or evidence([item], store, assumptions, context)[item["id"]], store, controls=controls)
    if favorites:
        export_wizard(items, proofs, review, assumptions)


def export_wizard(items, proofs, review, assumptions):
    with st.expander("Export selected favorites", expanded=True):
        chosen = st.multiselect("Products to export", [i["id"] for i in items],
                                format_func=lambda cid: next(i["product"].title for i in items if i["id"] == cid))
        if st.button("Select all favorites"):
            st.session_state["export_all_ids"] = [i["id"] for i in items]
        if st.checkbox("Use all favorites", value=bool(st.session_state.get("export_all_ids"))):
            chosen = [i["id"] for i in items]
        selected = [i for i in items if i["id"] in chosen]
        if not selected:
            st.caption("Select one or more favorites to preview an export.")
            return
        st.download_button("Download research workbook", research_workbook(selected, proofs, asdict(assumptions),
                           {i["id"]: review.history(i["id"]) for i in selected}), "favorite-research.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        from pof.settings import get_settings
        currencies = ["USD", "PAB"]
        store_currency = st.selectbox("Shopify store currency", currencies, index=currencies.index(get_settings(review.store)["currency"]))
        st.caption("Prices below must be in the selected store currency. No exchange conversion or publishing occurs. Import into a test store first; avoid overwriting existing matching handles.")
        draft = st.checkbox("Keep products as draft", value=True)
        exclude = st.checkbox("Exclude products with incomplete verification", value=True)
        editor = st.data_editor(pd.DataFrame([{"Candidate": i["id"], "Product": i["product"].title,
                    "Selling price": proofs.get(i["id"], {}).get("financial", {}).get("selling_price") if store_currency == "USD" else None}
                    for i in selected]), disabled=["Candidate", "Product"], hide_index=True,
                    column_config={"Selling price": st.column_config.NumberColumn(min_value=0.01)}, key="shopify_prices")
        prices = {r["Candidate"]: r["Selling price"] for r in editor.to_dict("records")}
        content, rows, report = shopify_export(selected, prices, exclude_incomplete=exclude, status="draft" if draft else "active", store_currency=store_currency)
        st.subheader("Shopify export preview")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        for result in report:
            if result["warnings"]:
                st.warning(result["title"] + (" — included for manual review: " if result["included"] else " — excluded: ") + "; ".join(result["warnings"]))
        st.caption(f"Validation: {len(rows)} included, {len(report)-len(rows)} excluded. Every row stays unpublished. CSV has no research-only columns; images without reuse permission are omitted.")
        st.download_button("Download Shopify CSV", content, "shopify-draft-products.csv", "text/csv", disabled=not rows)
        from pof.exporting import csv_bytes
        st.download_button("Download export validation report", csv_bytes(report), "shopify-validation.csv", "text/csv")
