# Review Center, Favorites and Settings

Baseline October 29, 2026: existing v2 branch at 181439d, clean checkout, 99 tests passed (three existing Streamlit/Pandas warnings). Reuse the existing SQLite snapshots, matching, finance, collection, keyword evidence and export/security helpers. Continue feature/v2-opportunity-discovery and its open PR; do not merge automatically.

Ratings are personal decisions, separate from matching reviews and opportunity scores. Migration 3 adds explicit review entities and snapshot associations with a SQLite online backup before migration. Product identities remain source-specific and conservatively distinguish known variants. No cross-source rating merge is inferred from similar titles. Expiring licensed snapshots still expire; personal ratings and notes can remain without expired listing payloads.

Shopify mapping checked against the official current CSV template and documentation on October 29, 2026: https://help.shopify.com/en/manual/products/import-export/using-csv and https://help.shopify.com/cdn/shopifycloud/product-knowledge/production/csv/product_template.csv. Use current headers, explicit variant dependencies, UTF-8, draft/unpublished status, original descriptions from verified specifications only and permitted images only. This is a local file export, not Shopify authentication, publishing or a store-side import test.
