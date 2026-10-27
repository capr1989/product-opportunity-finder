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
