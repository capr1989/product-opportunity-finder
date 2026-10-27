# Architecture decisions

The UI calls small deterministic domain modules and a single local persistence service. Dependencies point inward toward validated product snapshots. Connector protocol/registry isolates external collection from analysis. No dynamic plugin loading or downloaded code is permitted.

| Boundary | Module |
|---|---|
| UI and workflow | app.py |
| Normalization/provenance | pof/models.py, importing.py, extraction.py |
| Source adapters | pof/connectors.py |
| Browser lifecycle | pof/browser.py |
| API/demand | pof/demand.py |
| Search/discovery/comparison | pof/research.py |
| Product identity | pof/matching.py |
| Financial scenarios | pof/finance.py |
| Hard filters/preferences | pof/filters.py, scoring.py |
| Persistence/config/cache | pof/storage.py |
| Export | pof/exporting.py |
| Network/file/export security and event logging | pof/security.py |

SQLite migration 1 creates append-only product snapshots, runs, saved identities, configurations, reviews and cache tables. Migration versions are recorded. Future schema changes should add transactional versioned migration steps; do not reinterpret or overwrite old snapshots. WAL enables concurrent reads. Run IDs preserve original product payloads; latest views select the newest snapshot per stable source/role/URL-or-SKU identity. Demo flag is part of identity.

Structured JSON in SQLite is a deliberate tradeoff: flexible field schemas and auditable original records without many sparse columns. The snapshot envelope is stable. Normalize/index hot query fields if scale exceeds local limits. Current comparison is O(n²), capped at 1,000 products. No background scheduler is needed for explicit bounded research.

Financial arithmetic uses Decimal for intermediate calculations and serializes floats for UI/export. Historical source values and per-field provenance are separate from user assumptions and derived estimates. Ranking missing factors score zero to avoid rewarding missing data. Visual similarity is never identity evidence; known conflicts veto even matching identifiers. Manual match decisions persist with notes.

HTTP DNS pinning addresses DNS rebinding between validation and connection. The URL host becomes the checked IP; Host and TLS SNI retain the original hostname. Every retry revalidates DNS. Redirects are rejected rather than recursively trusting new destinations. Optional browser parsing receives a pre-fetched checked document; it cannot fetch subresources and runs with JS disabled, sandbox enabled, no persistent profile or downloads. This sacrifices dynamic extraction to reduce attack surface.

There is no optional AI runtime, purchasing, account mutation, campaign management, Shopify, alerts or scheduling. Those can later consume the snapshot/domain interfaces following separate threat reviews.
