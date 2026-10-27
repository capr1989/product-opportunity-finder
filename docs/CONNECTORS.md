# Connector development and data access

Built-in provider names are import-only registrations, not operational provider scrapers. Obtain access from each provider before implementing/using its API. Generic CSV/JSON/static page adapters work only for explicitly permitted endpoints and do not transmit authentication headers. APIs requiring signing/OAuth need a reviewed provider-specific adapter.

Implement `Connector.collect(source: dict, http: SafeHTTP) -> list[Product]`, register its kind in `REGISTRY`, and add the UI choice. The main research engine needs no changes. Use constructor injection for a test HTTP transport/client. Never load arbitrary plugin code from a user-entered path.

Every adapter must:

1. Validate typed fields and preserve original currency/identifiers. Mark observed, estimated, unavailable and stale fields honestly. Do not infer free shipping, single-unit MOQ, permission or availability from omissions.
2. Use SafeHTTP with exact configured host, public-only HTTPS and no redirects. Never bypass denied requests. For authenticated adapters, keep secrets outside source configuration and ensure only the intended provider receives them.
3. Bound page count, response size, concurrency and retries. Use source cooldown/cache. Never discover and crawl links unrestrictedly.
4. Return product records only; leave persistence to the collection workflow. Cached payload timestamps must not be reset as though freshly observed.
5. Add isolated tests for authorized success, missing credentials, denied/rate-limited access, malformed responses, oversized data, unsafe redirects and credential redaction.

JSON feeds contain an array of Product-field objects. CSV follows the same names. No transforms, Python expressions, shell commands or serialized Python objects are accepted. Product page extraction supports top-level schema.org Product JSON-LD or Product entries in an @graph, one unambiguous offer, reported price/currency and basic identifiers/ratings. AggregateOffer/range prices are not selected as unit quotes. Images are not fetched/rendered by default; records may retain URLs only where reuse permission is confirmed.

The optional browser adapter explicitly requires Chromium installation; it only parses static structured data. Pages requiring login, dynamic scripts or protection challenges should use a compliant authorized API/export/import alternative.

## Implemented live profiles

Best Buy native browser, Amazon public catalog and AliExpress public catalog were verified against actual products on October 27, 2026. `BestBuyConnector` is a separate optional official API adapter with contract tests but no live key verification. `run_research` always preserves real/demo separation, source-specific failure messages and observed timestamps.

Use InstallBrowser.cmd for the project-local official Chromium distribution. The native profile runs public site scripts in a sandbox with a scrubbed child environment and restricted same-origin reads. Amazon/AliExpress parse pre-fetched public HTML in JS-disabled DOMs. Do not extend the native request policy with state-changing operations, private credentials or arbitrary host access.

See SOURCE_ACCESS.md for actual failed probes and remaining integrations. A readable page is not verified product discovery; require observed product identity and price evidence and record their limits. Broad category search hints are distinguished from exact provider taxonomies. AliExpress minimum/coupon quotes and non-USD prices remain explicit and are not silently converted into confirmed supplier costs.
