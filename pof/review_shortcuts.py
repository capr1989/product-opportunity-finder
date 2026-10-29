"""Fixed first-party focus guard for Streamlit's global rating shortcuts.

No website content, product fields, secrets or user strings enter this script.
It stops application hotkeys in editable controls without preventing native edits.
"""
FOCUS_GUARD = """<script>
(() => {
  if (window.__pofReviewFocusGuard) return;
  window.__pofReviewFocusGuard = true;
  const guard = (event) => {
    const element = event.target;
    const editing = element instanceof Element && element.closest(
      'input, textarea, select, [contenteditable="true"], [role="combobox"], [role="spinbutton"]'
    );
    if (editing && (event.ctrlKey || event.metaKey) && event.shiftKey &&
        /^Digit[1-4]$/.test(event.code)) {
      event.stopImmediatePropagation();
    }
  };
  window.addEventListener('keydown', guard, true);
  window.addEventListener('keyup', guard, true);
})();
</script>"""
