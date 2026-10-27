# Live discovery validation — October 27, 2026

## Genuine public-source runs (no keys, no CSV, no demo substitution)

- **Best Buy keyword:** browser run 7 retrieved three `usb hub` listings, including a Belkin hub at USD 22.49 and an Insignia hub at USD 14.99, with stock indicators, source links and timestamps. The third price remained unknown.
- **Best Buy category:** run 11 used no product keyword and returned Sony headphones at USD 228.00 and Beats headphones at USD 199.99.
- **Amazon keyword:** run 8 returned five real offers, including Acer USD 9.87, Anker USD 7.99 and UGREEN USD 6.99 hubs, canonical ASIN links and timestamps.
- **Amazon broad:** run 10 used no product keyword and returned three Electronics-category offers, including cleaning accessories at USD 13.49 and USD 4.77.
- **AliExpress keyword:** run 8 returned five real supplier offers in PAB, including minimum/coupon prices 8.29 and 1.09. Currency is not relabeled as USD and minimum prices are not treated as confirmed unit costs.
- **AliExpress broad:** run 9 used no product keyword and returned three actual electronics-accessory offers.

These are observations at collection time, not guaranteed current prices, stock or eligibility. Records are in the local ignored SQLite database, not committed to Git. Source Manager records actual success/failure separately from installed-adapter status. The Best Buy API remains optional and has not been authenticated live.

## Blocked/unverified sources

CJ public requests redirected to its validation page; eBay returned HTTP 403; Alibaba returned a challenge document. No challenge bypass was attempted. Walmart redirected and Target returned HTML, but product extraction for those sources is not verified. Their names are not presented as functional integrations. Official API/partner routes were documented separately.

## Executed checks

- Latest full local suite: **86 passed**, including onboarding, all screens, Run Research/results/save/export, network/credential boundaries, currency/minimum-price handling and a real Chromium test of the observed Best Buy price widget.
- Ruff lint, pip dependency consistency, pip-audit and the heuristic secret scan passed. No new Python dependency was added.
- Chromium was installed explicitly from Playwright's official distribution into ignored project data. No administrator privileges, Defender changes, stealth patches or personal browser sessions were used.
- Tests use isolated temporary databases; contract fixtures are never written into the user's research library. Mock fixtures do not count as live verification.
- Three non-fatal Pandas deprecation warnings originate in Streamlit chart internals.
- Actual headless Chromium UI verification exercised New Research → Run Research → automatic Research Results with 50 real Amazon/AliExpress products, source failure reporting, currencies and minimum-quote warnings. Best Buy's Source Manager live test was then exercised through the actual UI and retrieved two products after a clean server restart. Screens were visually inspected locally.
- The long-running pre-upgrade server held an old model during hot edits. It was restarted after migration; application updates should be followed by a restart rather than relying on partial hot reloads of data-model classes.

The browser price extraction was corrected against actual current markup before calling Best Buy verified. Initial country-only pages and price-less cards were not accepted as complete product-price verification. The records above supersede the original import-first limitations documented below.

---

# Initial implementation validation — October 27, 2026

Local environment: Windows, isolated project virtual environment, CPython 3.12.14. Source folder was created in the user-requested development directory after Windows Controlled Folder Access blocked the original Documents workspace. Security protections were not modified.

## Functional milestones

1. Validated product snapshots, SQLite initialization/history, CSV imports, hard filters, deterministic financial scenarios and explicit demo mode: automated core tests passed.
2. Source manager, interchangeable normalized CSV/JSON and permitted static structured-data adapters, HTTP safety/caching and optional isolated browser boundary: fake-transport parsing and security tests passed. Provider-specific live access was not available and remains import-only.
3. Conservative identifier/variant matching, manual reviews, independently referenced deal detection, discovery/search and explainable scores: research tests passed, including stale-reference rejection and demo/real separation.
4. Official Google client request schema, read-only keyword ideas, optional historical metric presence, cooldown/cache, credential diagnostics and redacted errors: tests passed using actual installed request types and mocked service responses. No live OAuth or Cloud project authorization was tested.
5. Twelve Streamlit screens, demo research workflow, source history, formula-safe eight-sheet exports, Windows launch/install scripts, docs and CI: UI, export and security tests passed. No provider accounts or live advertising operations were used.

## Executed checks

- `python -m pytest -q`: **56 passed** at the final integration run before this record. This includes all twelve dashboard pages and the demo/search/deal workflow.
- `python -m ruff check .`: passed.
- `python -m pip check`: passed, no broken requirements.
- `python -m pip_audit`: no known vulnerabilities after updating inherited pip 25.0.1 to pinned pip 26.2.2.
- `python -m pip_audit -r requirements.lock --no-deps --disable-pip`: no known vulnerabilities in the fully pinned lock graph. This audits all 92 explicitly resolved packages without re-resolving them.
- Hash-locked installer dry run: completed without missing pins or dependency conflicts. A fresh-install CI run is a separate result; no remote CI success is claimed here.
- Heuristic secret scan: passed before initial commit; tracked candidates were reviewed for credentials, user data and machine-specific sensitive paths. The scanner is a baseline heuristic, not exhaustive secret detection.

Two non-fatal Pandas4Warning messages came from Streamlit's chart internals during demo history charts. They do not affect current behavior; monitor compatibility when upgrading Pandas/Streamlit. One initial cold UI test hit its 30-second startup timeout while dependency lock resolution was consuming CPU; the full suite subsequently passed without increasing the timeout.

## Unverified integrations / limits

- Actual retailer/supplier APIs, authentication, terms/access eligibility and live product equivalence.
- Live Google OAuth/customer/project authorization or keyword-planning access.
- Optional Chromium execution: binaries are not installed automatically. Browser mode is not required for import/feed/offline operation.
- Other Python/OS versions, multiuser deployment and public/LAN hosting. The supported launch target is Windows localhost, tested on Python 3.12.

No production sales, fulfillment or demand forecasts are asserted. See README and security documentation for assumptions and residual risks.
