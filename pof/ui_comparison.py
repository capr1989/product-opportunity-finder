"""Readable comparison panel; diagnostic payload is opt-in."""
import pandas as pd
import streamlit as st

from pof.comparison import amount, profit_explanation


def comparison_panel(a, b, row, summary):
    cols = st.columns(2)
    for column, label, product in ((cols[0], "Purchase listing", a), (cols[1], "Retail comparison", b)):
        with column:
            st.write(label)
            if product is None:
                st.write("No comparable retail listing found")
                continue
            st.text(product.title)
            st.write(product.source + " · " + amount(product.price, product.currency))
            st.caption("Observed " + product.collected_at)
    st.write("Product equivalence: " + summary["status"])
    st.caption(f"Match confidence: {row['match_confidence']:g}/100 (heuristic evidence score, not a probability).")
    st.caption("Source-reported attributes and matching rules are not an independent authenticity or fulfillment guarantee.")
    st.write("Why considered comparable: " + summary["why_comparable"])
    if summary.get("match_reason"):
        st.write("Matching rule: " + summary["match_reason"])
    if row.get("review") == "approve":
        st.info("You approved this match. That is your recorded judgment, not independent product verification; other missing costs and known conflicts still apply.")
    if summary["support"]:
        st.write("Agreeing evidence: " + "; ".join(summary["support"]))
    if summary["conflicts"]:
        st.warning("Conflicts: " + "; ".join(summary["conflicts"]))
    if summary["facts"]:
        st.table(pd.DataFrame(summary["facts"]))
    if summary["missing"]:
        st.write("Missing comparison information:")
        for message in summary["missing"]:
            st.text("• " + message)
    st.write("Purchase logistics")
    st.table(pd.DataFrame([
        {"Input": "Inbound shipping", "Reported value": amount(a.shipping, a.currency)},
        {"Input": "Minimum order quantity", "Reported value": f"{a.moq:g} ({a.state('moq')})" if a.moq is not None else "Unknown (not zero)"},
        {"Input": "Delivery days", "Reported value": str(a.delivery_days) if a.delivery_days is not None else "Unknown"},
        {"Input": "Destination", "Reported value": a.target_country or "Unconfirmed"},
        {"Input": "Stock", "Reported value": a.availability.replace("_", " ")},
        {"Input": "Price basis", "Reported value": str(a.source_attributes.get("price_basis") or "Not reported").replace("_", " ")},
    ]))
    st.caption("Destination is the requested selling market, not proof of shipping eligibility. Missing shipping is different from an explicit zero shipping quote.")
    st.write(profit_explanation(row, summary))
    st.write("Next step: " + summary["next_step"])
    st.caption("Use Investigate further to run the existing Deep Research workflow for this candidate.")
    with st.expander("Technical Details"):
        st.json({"purchase_specifications": a.specs, "retail_specifications": b.specs if b else {},
                 "purchase_identity": {"brand": a.brand, "model": a.model, "gtin": a.gtin, "sku": a.sku},
                 "retail_identity": {"brand": b.brand, "model": b.model, "gtin": b.gtin, "sku": b.sku} if b else {},
                 "purchase_field_states": a.states, "retail_field_states": b.states if b else {},
                 "purchase_price_basis": a.source_attributes.get("price_basis", "Not reported"),
                 "shipping": a.shipping, "MOQ": a.moq, "delivery_days": a.delivery_days,
                 "destination": a.target_country, "stock": a.availability,
                 "match_kind": row.get("match_kind"), "match_reason": row.get("match_reason"),
                 "candidate_similarity": row.get("similarity"), "match_confidence": row["match_confidence"]})
