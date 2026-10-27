"""Optional bounded Chromium parsing with JS disabled and public-network mediation."""
import threading
import os

from pof.security import MAX_RESPONSE, SafeHTTP

LOCK = threading.Lock()


def browser_env():
    """Do not pass application credential environment variables to Chromium children."""
    forbidden = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL", "AUTH", "PROXY")
    prefixes = ("GOOGLE_", "BESTBUY_", "CJ_", "EBAY_", "AWS_", "AZURE_")
    return {name: value for name, value in os.environ.items()
            if not name.upper().startswith(prefixes) and not any(word in name.upper() for word in forbidden)}


def extract_page(url: str, host: str, http: SafeHTTP) -> bytes:
    from pof.live.bestbuy_browser import configure_browser_path
    configure_browser_path()
    from playwright.sync_api import sync_playwright

    if not LOCK.acquire(blocking=False):
        raise ValueError("A browser session is already active")
    try:
        # Only the checked document is fulfilled. Every subresource/navigation is aborted.
        document = http.fetch(url, host, ("text/html", "application/xhtml+xml"))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, chromium_sandbox=True, env=browser_env())
            try:
                context = browser.new_context(java_script_enabled=False, accept_downloads=False,
                                              service_workers="block")
                page = context.new_page()
                served = False

                def route_request(route):
                    nonlocal served
                    if not served and route.request.url == url and route.request.is_navigation_request():
                        served = True
                        route.fulfill(body=document, content_type="text/html")
                    else:
                        route.abort()

                context.route("**/*", route_request)
                page.set_default_timeout(10000)
                page.goto(url, wait_until="domcontentloaded", timeout=10000)
                result = page.content().encode()
                if len(result) > MAX_RESPONSE:
                    raise ValueError("DOM exceeds size limit")
                return result
            finally:
                browser.close()
    except ImportError:
        raise ValueError("Playwright is not installed") from None
    finally:
        LOCK.release()
