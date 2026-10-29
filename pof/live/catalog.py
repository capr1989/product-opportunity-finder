"""Evidence-based access catalog. Entries describe routes, not implemented integrations."""
from pof.models import now

POLICIES = {
    "Best Buy": {"method": "Live Scraping", "connector": "Public-page browser and optional Products API implemented; live verification pending",
        "reason": "Public browser mode needs no key. Site terms may restrict automation, and pages can be blocked or unreadable. Access challenges stop collection without evasion.",
        "url": "https://www.bestbuy.com/site/help-topics/terms-and-conditions/pcmcat204400050067.c?id=pcmcat204400050067",
        "setup": "Browser mode is the default and uses ordinary sandboxed Chromium with no stored login or API key. Optional API: https://developer.bestbuy.com/ → Get API Key. Actual retrieval must succeed before this source is called verified.",
        "implemented": True, "credential": "BESTBUY_API_KEY"},
    "CJdropshipping": {"method": "Restricted", "connector": "Public catalog access tested; no working product adapter verified",
        "reason": "The public catalog request redirected to CJ's validation page. Collection stopped without bypassing it. The official API is a separate optional authorized route.",
        "url": "https://developers.cjdropshipping.com/en/api/start/apikey.html",
        "setup": "CJ account → Apps → Install App → Others → API. Then Authorization/API → Add API → Type API Key → Confirm → Copy. Documentation: https://developers.cjdropshipping.com/en/api/api2/api/product.html",
        "implemented": False, "credential": ""},
    "Amazon US": {"method": "Live Scraping", "connector": "Public server-rendered catalog adapter implemented; verification recorded separately",
        "reason": "Key-free public catalog collection uses bounded HTTP and sandboxed Playwright DOM parsing. Access barriers stop collection. Broad discovery defaults to the Electronics catalog.",
        "url": "https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction",
        "setup": "No API key is required for the implemented public-page method. Select this source in New Research. Creators API remains a separate optional future route requiring eligibility and credentials.",
        "implemented": True, "credential": ""},
    "Walmart": {"method": "Access pending", "connector": "Public request redirected; product extraction not verified",
        "reason": "Site terms restrict automated collection without permission. Seller Marketplace catalog search requires approved access and does not itself guarantee consumer prices.",
        "url": "https://www.walmart.com/help/article/walmart-com-terms-of-use/3b75080af40340d6bbd596f116fae5a0/",
        "setup": "Review Walmart Developer Portal and approved partner/seller access. A seller account is not automatically permission for every retail-data use.",
        "implemented": False, "credential": ""},
    "Target": {"method": "Access pending", "connector": "Public HTML retrieved; product extraction not verified",
        "reason": "Terms restrict automated product-data collection. Approved agents' access does not grant this local application permission.",
        "url": "https://www.target.com/c/terms-conditions/-/N-4sr7l",
        "setup": "Obtain a licensed partner feed or written automation permission before enabling an adapter.",
        "implemented": False, "credential": ""},
    "eBay US": {"method": "Restricted", "connector": "Browse API route identified; not implemented or verified",
        "reason": "User agreement requires permission for automated scraping. Official Browse API uses an application access token.",
        "url": "https://developer.ebay.com/api-docs/buy/browse/overview.html",
        "setup": "Join eBay Developers Program, create production app credentials, and confirm Buy API production eligibility. Review https://www.ebay.com/help/policies/member-behavior-policies/user-agreement?id=5414",
        "implemented": False, "credential": ""},
    "Alibaba": {"method": "Access pending", "connector": "Partner/open-platform access needs confirmation",
        "reason": "No permitted anonymous catalog extraction route has been established for this application.",
        "url": "https://open.alibaba.com/", "setup": "Confirm approved partner API/feed access or obtain written collection permission. No functional integration is claimed.",
        "implemented": False, "credential": ""},
    "AliExpress": {"method": "Live Scraping", "connector": "Public catalog adapter implemented; verification recorded separately",
        "reason": "Key-free public catalog collection preserves reported currency and minimum/coupon price conditions. Shipping, variants and final unit costs stay unconfirmed.",
        "url": "https://open.aliexpress.com/", "setup": "No API key is required for the public-page method. Select AliExpress in New Research. Listed minimum prices are not treated as confirmed unit costs for profit calculations.",
        "implemented": True, "credential": ""},
}


def bestbuy_browser_mode(config, has_key):
    mode = config.get("bestbuy_method", "api" if has_key else "browser")
    return mode in {"browser", "browser-first"} or (mode in {"auto", "api-first"} and not has_key)


def source_status(name, config, state, has_key=False):
    policy = POLICIES.get(name, {})
    configured = config.get("kind") in {"json", "csv", "public_page", "browser", "browser_catalog"}
    browser_mode = name == "Best Buy" and bestbuy_browser_mode(config, has_key)
    method = "Live Scraping" if browser_mode else "Live API" if name == "Best Buy" else policy.get("method", "Import Only")
    ready = (name == "Best Buy" and (browser_mode or has_key)) or name in {"Amazon US", "AliExpress"}
    if state.get("error_code") in {"access_denied", "access_barrier", "credentials_rejected"}:
        method = "Restricted"
    if configured and config.get("permission_confirmed") and (config.get("url") or config.get("search_url_template")):
        method = "Live Scraping" if config["kind"] in {"browser", "public_page", "browser_catalog"} else "Live Feed"
        ready = True
    verified = state.get("verified_live", False)
    last_success = state.get("last_success", "Never")
    if name == "Best Buy" and not browser_mode and not configured:
        # A successful browser collection does not authenticate the API route.
        api_proof = state.get("verified_methods", {}).get("bestbuy_api", {})
        verified = bool(api_proof)
        last_success = api_proof.get("last_success", "Never")
    return {"Source": name, "Collection method": method, "Connector available": bool(ready or policy.get("implemented")),
        "Credentials": "Not required (browser mode)" if browser_mode or name in {"Amazon US", "AliExpress"} else "Required for optional API" if name == "Best Buy" and not has_key else "Configured" if has_key else "Not requested",
        "Verification": "Actual products retrieved" if verified else "Not live-verified",
        "Last successful collection": last_success,
        "Last error": state.get("last_error", ""), "Products last found": state.get("last_count", 0),
        "Enabled": config.get("enabled", True), "ready": ready and config.get("enabled", True)}


def record_attempt(store, name, *, count=0, error="", code="", live=False, method=None):
    previous = store.get_config("collection_state", name) or {}
    state = {**previous, "last_attempt": now(), "last_count": count, "last_error": error, "error_code": code}
    if not error and live and count:
        state.update(last_success=now(), verified_live=True)
        if method:
            methods = state.get("verified_methods", {}).copy()
            methods[method] = {"last_success": now(), "count": count}
            state["verified_methods"] = methods
    elif not error:
        state["last_note"] = "Request completed; no products matched" if not count else "Results from cache"
    store.put_config("collection_state", name, state)
    return state
