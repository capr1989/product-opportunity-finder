# Product Opportunity Finder

A local-first Windows research application for comparing supplier and retail products, estimating contribution profit, and organizing research opportunities. Python 3.12+, Streamlit, SQLite. No cloud services are required for offline analysis. No automatic buying, campaign creation, Shopify integration or business execution.

## Live-first workflow

**V2 starts at Find Products Worth Selling.** Click **Run Quick Scan** without entering keywords: working source routes are selected automatically and searches rotate across categories. **Deep Research** investigates selected or saved candidates with focused cross-source searches. **Guided Research** adds business model, market, budget, desired profit and delivery preferences. All prior screens are under **Advanced Tools**. See [v2 workflow, validation and limits](docs/V2.md).

Results distinguish **Potential Lead**, **Financially Evaluated** and **Rejected / Unattractive**. A listing price difference is never labeled profit. Missing shipping, MOQ, identity, currency or selected-variant costs remain visible with a next step. Save candidates, investigate several together, review matches, dismiss findings, or resume interrupted research. Existing history and imports remain available.

Use **Start New Research → select sources/filters → Run Research → Research Results**. CSV is an optional fallback. New users receive a setup wizard for USA/Panama markets, connections and costs; built-in Help covers the workflow.

**Live-verified without API keys:** Best Buy, Amazon US and AliExpress. Real runs retrieved product names, observed prices, source links and timestamps. Both keyword research and discovery without specific product names were exercised. Best Buy returned USD offers; Amazon returned USD offers; AliExpress returned PAB minimum/coupon offers, which are preserved as such and excluded from automatic unit-profit calculations. See [validation evidence](docs/VALIDATION.md).

Best Buy also has an optional official Products API adapter, tested against its documented schema but not authenticated live. No API key is required for the implemented public-page methods. CJdropshipping redirected to a validation page; eBay denied the HTTP probe; Alibaba returned a challenge document. Walmart and Target product extraction is not verified. Those are not presented as functioning connectors.

The native browser uses a sandbox, ephemeral session, pinned public hostname, ordinary website scripts and transparent app identification. It performs no account/purchase requests, CAPTCHA solving, stealth, proxy rotation or login automation. Website terms may restrict automation; technical barriers stop collection. See [user guide](docs/USER_GUIDE.md) and [source assessment](docs/SOURCE_ACCESS.md).

## Start on Windows

1. Prefer a dedicated Windows VM and a standard user account; see [VM setup](docs/WINDOWS_VM.md).
2. Install Python 3.12+ from python.org. Use a writable development directory outside protected Documents when Controlled Folder Access blocks development tools. Keep Windows security protections enabled.
3. Double-click `Install.cmd`. It creates `.venv` and installs the hash-locked dependencies. The initial installation needs internet access. It does not download Chromium or install global tools.
4. Double-click `Launch.cmd`. The dashboard opens at **http://127.0.0.1:8501**. Keep the terminal open; Ctrl+C stops the server. Refresh the browser if it opens before startup completes.
5. Run `InstallBrowser.cmd` once for key-free collection. Its official Chromium download goes into the ignored `data/browsers/` folder without global changes or administrator privileges.
6. Complete or skip Setup. In Source Manager choose Best Buy public browser mode, then click **Start New Research**. Select sources/filters and **Run Research**; inspect actual results/errors.
7. For fictional examples, explicitly enable **Demo dataset → Load / reset demo snapshots**. Live screens always turn demo off. Optional CSV imports remain under Advanced source configuration.

For an existing venv, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
```

SQLite initializes automatically in `data/research.sqlite3`. Data, logs, local credentials and virtual environments are ignored by Git. Copy `data/` while the application is stopped to back up research. Offline search, matching, financial scenarios, saved products, history and exports use collected snapshots.

## Research workflow

- **Product Search:** search titles, identifiers, models, brands, categories and SKUs in the local library.
- **Broad Discovery:** browse categories and sources without a product keyword. Start New Research collects live products using category search hints or provider taxonomy; the older Broad Discovery screen searches the collected library.
- **Retail Deal Hunter:** compare fresh, verified prices for exact matches from independent merchants; advertised original prices alone never establish a deal.
- **Dropshipping Opportunities / Product Comparison:** compare supplier-to-retailer or retailer-to-retailer purchase scenarios, review matches and inspect score factors.
- **Hard filters:** two graphical AND/OR groups with up to 15 rules each; the engine supports nesting to eight levels. Excluded keywords/brands use `not_contains`/`ne`. Each rule chooses whether unknowns are included with warnings or excluded. Save/apply/reset presets.
- **Cost assumptions:** edit every implemented per-order cost and rate in the sidebar. Ranking preferences are separate from hard filters.
- **Google Ads Keyword Research:** read-only keyword ideas, historical searches/trends, competition and bid ranges; explicit manual association with products. CSV alternative works without API access. See [Google setup](docs/GOOGLE_ADS.md).
- **Research History:** immutable snapshots, run comparisons, new products and price changes. Repeated cached collection retains the original collection timestamp.
- **Export Center:** CSV and eight-sheet Excel workbooks with assumptions, source references, field states, match confidence and score explanations.

## Connector status

Best Buy, Amazon US and AliExpress have live-verified public-page adapters. The optional Best Buy API is implemented but not authenticated live. CJdropshipping, Walmart, Target, eBay and Alibaba have documented probe results and limitations; none is claimed as a working connector. Other registrations remain import-only. Source Manager separates implementation, actual verification and the latest failure.

Generic adapters support normalized JSON/CSV feeds, static Product JSON-LD pages, and bounded browser catalogs with source-specific URL templates and product-link paths. Generic browser parsing keeps JS disabled and checks robots rules. Best Buy native browsing runs normal same-host scripts in sandboxed Chromium with restricted networking. Neither route uses CAPTCHA solving or unrestricted crawling.

Source Manager reports collection method, credentials when needed, actual verification, last successful collection and last error. Optional Best Buy API keys are password-masked and kept only in the current browser session, or read from BESTBUY_API_KEY. They are never persisted in SQLite, logs or Git. Browser mode requires no key. See [connector guide](docs/CONNECTORS.md).

## Data contract

Product CSV requires `source,title`; download the complete column template in Source Manager. Optional columns match `pof.models.Product`. Use `role=supplier` or `retailer`, ISO 8601 timezone-aware timestamps, `true`/`false` booleans and JSON objects for `specs` and `states`. UTF-8, maximum 10 MiB and 10,000 rows. GTIN/SKU/model remain strings. Empty numeric fields are unknown, not zero. Currency must be explicitly USD for financial comparison. Default imported currency is USD; change it when appropriate.

Important conventions:

- `price` is **per-unit**; `shipping` is inbound **per-unit** cost, not total shipment cost. `moq` is integer units. Inventory commitment = landed cost × MOQ; contribution economics are per unit.
- Cost assumptions are user estimates. Duty applies to product cost; nonrecoverable import tax applies to product + freight + duty. Payment/platform/return allowances apply to sale revenue. Return allowance models revenue reserve, not a full return-logistics model.
- All unspecified field states default to **estimated**. Set `states={"price":"verified"}` only when supported by evidence. Verified means observed/reported by the source, not independently audited or guaranteed true. Fields older than seven days are **stale**; missing values are **unavailable**.
- Financial outputs require compatible USD prices, known inbound shipping, known MOQ and an exact/equivalent or manually approved match. Advertised minimum/coupon supplier prices are not confirmed unit costs and are excluded from automatic profitability. Unverified comparisons do not receive profit estimates. Manual approval is your recorded judgment.
- Bid ranges are not measured CPC and remain labeled in the Google Ads account currency. No currency conversion is performed. Keyword demand is not sales demand for an individual product.

## Financial and ranking methods

Gross profit = sale price − landed product cost. Contribution profit additionally subtracts payment fees, platform fees, returns allowance, advertising, outbound fulfillment and other cost. Gross/contribution margins use sale revenue. ROI uses total estimated unit cash cost including fees and advertising. Break-even CAC is contribution before advertising; break-even CPC multiplies that by conversion rate. Negative break-even values indicate loss even without advertising. Zero denominators return unknown ratios.

Scores use normalized nonnegative weights for profitability, verified keyword demand, advertising competition, fulfillment speed, supplier rating/review proxies, match confidence, freshness and uncertainty. Missing factors score zero; weights are not redistributed. Competition is keyword advertising competition, **not** a measured count of competing sellers. Reliability is a limited rating/review proxy. Scores prioritize research; they do not predict sales.

## Validation and maintenance

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit -r requirements.lock
.\.venv\Scripts\python.exe tools/scan_secrets.py
```

`requirements.in` pins direct dependencies; `requirements.lock` pins and hashes the resolved Windows/Python 3.12 dependency graph. Update deliberately in a clean Python 3.12 environment: review direct pins, install them, run `python tools/lock_dependencies.py`, inspect the diff, audit and rerun tests. The lock generator freezes the reviewed installed graph and retrieves SHA256 release hashes from PyPI; it never installs packages. Python 3.12 is the tested version; other 3.12+ versions require compatibility verification. Do not enable automatic dependency upgrades. A passing audit is a point-in-time result, not a security guarantee. CI runs lint, tests, an audit and a local heuristic secret scan using read-only workflow permissions and SHA-pinned actions. Enable GitHub's private-repository secret scanning if your account plan supports it.

Major packages: Streamlit (UI), HTTPX (bounded HTTP), Playwright (sandboxed browser/DOM collection), SQLite stdlib (history), Pandas (tables), RapidFuzz (matching), OpenPyXL (safe exports), google-ads (official API client), Pytest (tests), Ruff (lint), pip-audit (advisories), pip-tools (reproducible lock).

## Limitations and remaining verification

- Three public-page sources were live-verified on October 27, 2026, but websites can change or deny later requests. Other providers and live Google OAuth remain unverified. No ongoing-access guarantee is made.
- Generic feeds must already follow the normalized schema. Static page extraction is intentionally narrow: one unambiguous Product offer; shipping, tax, stock feasibility and MOQ may remain unknown. Dynamic pages often require a permitted API/import instead.
- No forex conversion, sold-item marketplace demand, automated shipping eligibility or authenticated retailer sessions are included; the optional Best Buy API adapter is separately implemented. Unknown logistics are visible and can be excluded with filters. MOQ>1 may be unsuitable for direct fulfillment; filter appropriately.
- Scoring and financial comparisons are scenario analysis, not a guarantee of fulfillment, authenticity, legality or profitability. Delivery/availability need independent verification.
- Pairwise analysis is capped at 1,000 products. Narrow datasets before comparison/export. Imports are capped at 10,000 rows.
- One local user; browser collection concurrency is bounded per adapter. No LAN/multiuser deployment or application login. Local files rely on Windows account permissions and disk protection, not application encryption.
- Browser installation is explicit through `InstallBrowser.cmd`. The generic static parser has JS disabled; native Best Buy browsing executes website JS inside a sandboxed ephemeral context. Browser/parser vulnerabilities remain a risk; use the dedicated research VM.

See [architecture](docs/ARCHITECTURE.md), [security policy](SECURITY.md), [threat model](docs/THREAT_MODEL.md) and [validation record](docs/VALIDATION.md). The repository is intended to remain **private and unlicensed**; no open-source license is granted.
