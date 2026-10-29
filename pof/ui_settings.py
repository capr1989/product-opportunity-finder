"""Central settings and credential configuration with provider-scoped tests."""
from dataclasses import asdict
import platform
import sqlite3
import sys

import pandas as pd
import streamlit as st

from pof.credential_vault import CredentialVault, FIELDS, integration_credentials, masked_status
from pof.demand import REQUIRED, keyword_ideas
from pof.finance import Assumptions
from pof.live.query import ResearchQuery
from pof.models import now
from pof.opportunity_engine import TAXONOMY
from pof.settings import DEFAULTS, get_settings, save_settings
from pof.ui_live import connect_sources, connection_rows

VERSION = "0.3.0"


def test_integration(store, provider):
    values = integration_credentials(provider)
    required = ("BESTBUY_API_KEY",) if provider == "Best Buy" else REQUIRED
    if not all(values.get(k) for k in required):
        result = {"status": "Not tested", "explanation": "Required credentials are missing", "tested_at": now()}
        store.put_config("integration_test", provider, result)
        return result
    try:
        if provider == "Best Buy":
            # Explicitly test the official API without changing saved browser preferences.
            from pof.live.bestbuy import BestBuyConnector
            products = BestBuyConnector(values["BESTBUY_API_KEY"]).discover(ResearchQuery(keywords="usb hub", limit=1, max_pages=1))
            if products:
                store.add_run("Best Buy API connection test", products)
            count = len(products)
        else:
            rows, _ = keyword_ideas(store, ["usb hub"])
            count = len(rows)
        result = {"status": "Actual data retrieved" if count else "Request completed; no data returned",
                  "records": count, "tested_at": now(), "explanation": "Entering credentials alone does not verify an integration"}
    except Exception:
        result = {"status": "Test failed", "explanation": "Check credential validity, account access, quota and provider setup instructions. Secret-bearing response details are hidden.", "tested_at": now()}
    store.put_config("integration_test", provider, result)
    return result


def credential_manager(store):
    st.caption("Windows Credential Manager stores secrets for your Windows account. No plaintext fallback, SQLite secret storage or automatic OAuth enrollment is used.")
    provider = st.selectbox("Credential provider", list(FIELDS))
    st.table(pd.DataFrame([{"Field": name, "Status": status} for name, status in masked_status(provider).items()]))
    if provider == "Google Ads":
        st.write("Use your own Google Cloud OAuth client, authorize the Google Ads scope, obtain a refresh token and grant access to the intended Ads customer. This app uses the existing read-only keyword-planning integration.")
        st.link_button("Google OAuth setup", "https://developers.google.com/google-ads/api/docs/oauth/overview")
    else:
        st.write("Best Buy public browser collection needs no key. The optional official API requires a developer key.")
        st.link_button("Best Buy API access", "https://developer.bestbuy.com/")
    st.caption("Leave a field blank to keep its saved value. Environment variables take precedence and must be removed outside the app if no longer wanted.")
    with st.form("credential_form", clear_on_submit=True):
        entered = {name: st.text_input(name, type="password", autocomplete="off") for name in FIELDS[provider]}
        save = st.form_submit_button("Save or replace credentials")
    if save:
        try:
            vault = CredentialVault()
            values = vault.load(provider)
            values.update({k: v.strip() for k, v in entered.items() if v.strip()})
            if not values:
                st.warning("Enter at least one credential field")
            elif provider == "Google Ads" and values.get("GOOGLE_ADS_CUSTOMER_ID") and (not values["GOOGLE_ADS_CUSTOMER_ID"].isdigit() or len(values["GOOGLE_ADS_CUSTOMER_ID"]) != 10):
                st.warning("Google Ads customer ID must contain 10 digits without dashes")
            else:
                vault.save(provider, values)
                st.success("Saved securely to Windows Credential Manager. Test Connection to check actual access.")
        except (ValueError, OSError):
            st.error("Windows Credential Manager could not save the credentials. No plaintext copy was saved. Check your Windows account's credential-storage access.")
    if st.button("Remove saved credentials"):
        try:
            CredentialVault().remove(provider)
            if provider == "Best Buy":
                st.session_state.pop("source_credentials", None)
            st.success("Saved Windows credentials removed. Environment overrides, if any, are managed outside this app.")
        except (ValueError, OSError):
            st.error("Windows could not remove this credential entry")
    if st.button("Test Connection"):
        result = test_integration(store, provider)
        st.info(result["status"] + ": " + result["explanation"])
    result = store.get_config("integration_test", provider)
    if result:
        st.caption("Last test: " + result["tested_at"] + " · " + result["status"])
    st.caption("CJdropshipping and eBay credentials are not accepted: those connectors are not implemented. Their access limits remain in Source Manager.")


def application_settings(store):
    st.title("Settings")
    general, research, sources, credentials, financial, security = st.tabs(
        ["General", "Research", "Sources and Integrations", "API Credential Manager", "Financial Assumptions", "Security and Diagnostics"])
    current = get_settings(store)
    with general:
        st.caption("Source currencies stay as reported. Preferred currency changes display/export preferences; it does not convert quotes.")
        with st.form("general_defaults"):
            market = st.selectbox("Default selling market", ["US", "PA", "US+PA"], index=["US", "PA", "US+PA"].index(current["market"]))
            currency = st.selectbox("Preferred currency", ["USD", "PAB"], index=["USD", "PAB"].index(current["currency"]))
            model = st.selectbox("Default business model", ["Explore All", "Dropshipping", "Retail Reselling", "Wholesale"], index=["Explore All", "Dropshipping", "Retail Reselling", "Wholesale"].index(current["business_model"]))
            mode = st.selectbox("Default scan behavior", ["Quick Scan", "Deep Research"], index=["Quick Scan", "Deep Research"].index(current["default_mode"]))
            images = st.checkbox("Display permitted product images", current["show_images"])
            if st.form_submit_button("Save general preferences"):
                save_settings(store, {"market": market, "currency": currency, "business_model": model, "default_mode": mode, "show_images": images})
                st.success("Defaults saved for new research screens")
        st.text("Active local data directory: " + str(store.path.parent))
        st.caption("To use another directory, set POF_DATA_DIR before launching. Existing data is not automatically moved or overwritten. Back up below before changing directories.")
    with research:
        with st.form("research_defaults"):
            quick = st.number_input("Quick Scan search limit", 1, 12, current["quick_queries"])
            deep = st.number_input("Deep Research search limit", 1, 12, current["deep_queries"])
            maximum_sources = st.number_input("Maximum sources", 1, 5, current["source_limit"])
            products = st.number_input("Products per source per search", 1, 20, current["products_per_source"])
            st.number_input("Concurrent collections", 1, 1, 1, disabled=True, help="Collectors run sequentially to preserve browser isolation and provider request limits.")
            cache = st.number_input("Reuse recent successful collection (seconds; 0 = refresh)", 0, 900, current["cache_seconds"])
            categories = st.multiselect("Default product categories", list(TAXONOMY), default=current["categories"])
            excluded = st.multiselect("Excluded categories", list(TAXONOMY), default=current["excluded_categories"])
            preset = st.text_input("Optional preset name", max_chars=100)
            if st.form_submit_button("Save research defaults"):
                try:
                    values = save_settings(store, {"quick_queries": quick, "deep_queries": deep, "source_limit": maximum_sources,
                        "products_per_source": products, "cache_seconds": cache, "categories": categories, "excluded_categories": excluded})
                    if preset.strip():
                        store.put_config("research_defaults_preset", preset.strip(), values)
                    st.success("Research defaults saved")
                except ValueError as exc:
                    st.warning(str(exc))
        presets = store.configs("research_defaults_preset")
        if presets:
            name = st.selectbox("Saved search preset", list(presets))
            if st.button("Use search preset"):
                save_settings(store, presets[name])
                st.success("Preset applied")
    with sources:
        connect_sources(store)
        st.subheader("Best Buy access preference")
        config = store.get_config("source", "Best Buy")
        preference_names = ["Automatic", "Browser first", "API first", "Browser only", "API only"]
        preference_modes = ["auto", "browser-first", "api-first", "browser", "api"]
        mode = st.selectbox("Collection preference", preference_names,
                            index=preference_modes.index(config.get("bestbuy_method", "auto")))
        if st.button("Save access preference"):
            config["bestbuy_method"] = {"Automatic": "auto", "Browser first": "browser-first", "API first": "api-first", "Browser only": "browser", "API only": "api"}[mode]
            store.put_config("source", "Best Buy", config)
            st.success("Access preference saved. API requires configured credentials; browser mode does not.")
    with credentials:
        credential_manager(store)
    with financial:
        costs = store.get_config("settings", "costs") or asdict(Assumptions())
        with st.form("central_costs"):
            updated = {}
            for name, value in costs.items():
                updated[name] = st.number_input(name.replace("_", " ").title(), 0.0, 1.0 if name.endswith("rate") else 100000.0,
                    float(value), key="central_" + name,
                    help="Your cost assumption, not a supplier quotation. Rates are fractions: 0.15 means 15%. Platform rate can represent your applicable marketplace/Shopify fee assumption.")
            budget = st.number_input("Inventory budget (USD)", 0.0, 1_000_000.0, current["budget"])
            profit = st.number_input("Target contribution per unit (USD)", 0.0, 1_000_000.0, current["minimum_profit"])
            margin = st.number_input("Target contribution margin (%)", 0.0, 100.0, float(current["minimum_margin"]))
            scenario_name = st.text_input("Financial scenario name", max_chars=100)
            if st.form_submit_button("Save financial assumptions"):
                Assumptions(**updated)
                store.put_config("settings", "costs", updated)
                save_settings(store, {"budget": budget, "minimum_profit": profit, "minimum_margin": margin})
                if scenario_name.strip():
                    store.put_config("financial_scenario", scenario_name.strip(), updated)
                st.success("Financial assumptions saved separately from observed costs")
        scenarios = store.configs("financial_scenario")
        if scenarios:
            chosen = st.selectbox("Saved financial scenario", list(scenarios))
            if st.button("Use financial scenario"):
                store.put_config("settings", "costs", scenarios[chosen])
                for key in list(st.session_state):
                    if key.startswith("central_"):
                        del st.session_state[key]
                st.rerun()
        if st.button("Reset financial defaults"):
            store.put_config("settings", "costs", asdict(Assumptions()))
            save_settings(store, {k: DEFAULTS[k] for k in ("budget", "minimum_profit", "minimum_margin")})
            for key in list(st.session_state):
                if key.startswith("central_"):
                    del st.session_state[key]
            st.rerun()
    with security:
        st.write(f"Application version {VERSION} · Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} · {platform.system()}")
        st.write("Supported launcher binds to 127.0.0.1. Browser sandboxing, request bounds and source access restrictions remain enabled.")
        address = st.get_option("server.address")
        st.write("Configured server address: " + str(address or "Not explicitly configured"))
        if address != "127.0.0.1":
            st.warning("Local-only binding is not confirmed. Restart using Launch.cmd or explicitly bind server.address to 127.0.0.1.")
        st.caption("Do not override server.address for public/LAN hosting. Windows security settings are never modified by this application.")
        st.code(".\\.venv\\Scripts\\python.exe -m pytest -q\n.\\.venv\\Scripts\\python.exe -m ruff check .\n.\\.venv\\Scripts\\python.exe -m pip check\n.\\.venv\\Scripts\\python.exe -m pip_audit -r requirements.lock\n.\\.venv\\Scripts\\python.exe tools/scan_secrets.py", language="powershell")
        rows = connection_rows(store)
        st.dataframe(pd.DataFrame([{k: r[k] for k in ("Source", "Collection method", "Verification", "Last successful collection", "Last error")} for r in rows]), hide_index=True)
        st.caption("Diagnostics show only application-generated source errors and masked credential state. Raw provider responses, credential-bearing URLs and arbitrary log contents are not displayed.")
        if st.button("Prepare database backup"):
            if store.path.stat().st_size > 200_000_000:
                st.warning("For a database this large, stop the app and copy the data directory using Windows.")
            else:
                with store.connect() as db, sqlite3.connect(":memory:") as destination:
                    db.backup(destination)
                    backup = destination.serialize()
                st.download_button("Download research database backup", backup, "research-backup.sqlite3", "application/octet-stream")
                st.caption("Keep backups private. They include research, personal ratings and notes, but no Windows vault credentials. Restore only with the application stopped; keep the current database until validation succeeds.")
