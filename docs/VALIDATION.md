# Validation record — October 27, 2026

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
