import pytest

from pof.live.bestbuy_browser import browser_installed, configure_browser_path
from pof.review_shortcuts import FOCUS_GUARD


@pytest.mark.skipif(not browser_installed(), reason="Optional project Chromium is not installed")
def test_rating_focus_guard_preserves_text_editing_and_outside_shortcuts():
    from playwright.sync_api import sync_playwright
    configure_browser_path()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            page = browser.new_page()
            page.set_content('<textarea aria-label="Notes"></textarea><button>Outside</button>')
            page.add_script_tag(content=FOCUS_GUARD.removeprefix("<script>").removesuffix("</script>"))
            page.evaluate("window.count=0; window.addEventListener('keydown', e => { if(e.ctrlKey && e.shiftKey && e.code==='Digit2') window.count++; });")
            notes = page.get_by_role("textbox", name="Notes")
            notes.fill("My notes 1234")
            notes.press("Control+Shift+2")
            assert page.evaluate("window.count") == 0
            assert notes.input_value() == "My notes 1234"
            page.get_by_role("button", name="Outside").click()
            page.keyboard.press("Control+Shift+2")
            assert page.evaluate("window.count") == 1
        finally:
            browser.close()
