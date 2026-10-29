# Focused Quick Scan comparison correction

## Cause and trace

The issue originated before persistence. The public Amazon, Best Buy and AliExpress adapters primarily collected search-card names, prices and source-specific identifiers; they did not populate `Product.specs`. The generic JSON-LD parser also omitted additional properties and dimensions. The optional Best Buy API retained manufacturer/model/UPC separately, but omitted supplied detail properties. In the inspected live library, 251 latest product records had zero nonempty `specs` dictionaries; 36 had brand data and none had a structured model. Those counts describe the inspection, not a guaranteed future dataset.

`Product.record()` includes specs, brand/model, identifiers and source attributes. `Store.add_run()` serializes them into immutable snapshot payloads; `Store.products()` restores them; `session_products()` retains them. Round-trip tests confirm these layers do not discard specifications. The old panel displayed only the empty spec dictionaries and a few logistics fields, hiding useful separately stored identities and the original titles. Original HTML/bootstrap responses are not retained, so unavailable old attributes cannot be reconstructed retrospectively.

## Correction

- Bounded explicit label/property extraction now preserves brand, model, GTIN/UPC/EAN and available color, material, package quantity, dimensions and other scalar specifications. Search-card labels/data attributes, supplied API/bootstrap fields and Product JSON-LD additional properties are supported. No first-word brand guesses or inferred title models are promoted into verified source fields. Unselected variant-option lists are not selected as specifications. No extra crawling, source/API access or request-budget changes were added; the Best Buy API's requested field list remains unchanged.
- The existing comparison expander now shows purchase/retail names, sources, prices/timestamps, identity/specification evidence, conflicts, confidence, candidate similarity, missing information and an equivalence assessment. Source-specific listing IDs are distinguished from shared product identifiers. Missing specs are explicit, and title-derived clues are labeled unverified. Original payload details remain under a closed Technical Details expander.
- Profit explanations enumerate the actual blockers already enforced by the engine: equivalence, shipping, MOQ, currency, price/condition freshness, stock, selected-variant cost or fulfillment/market requirements. An explicit zero is retained as a value. A price gap never substitutes for contribution profit.
- Next steps target the first actionable issue (model/variant conflict, identity, selected unit cost, shipping, availability or additional retail offers). Investigate further continues the existing Deep Research workflow; match approval, saves and dismissals remain available.

## Matching correction

The observed USD 27.99/33.99 library contains Logitech M510 and M650 mouse listings. Their structured model fields were blank, but their titles stated different model codes. A conservative veto now recognizes unambiguous same-brand, same-code-family title conflicts without writing those clues into `Product.model` or using them to grant equivalence. This pair is contradicted and cannot become a financial opportunity, including through a manual approval that leaves the conflict unresolved.

A second safeguard prevents title-derived capacity/package clues alone from satisfying the fuzzy “equivalent” rule: explicit specification dictionaries are required for that branch. Existing exact identifiers, known variant conflicts, manual review controls, financial arithmetic, scoring weights and immutable records are preserved. This is a correction to evidence handling, not a new discovery engine.

## Validation and limitations

Baseline: 117 tests passed. Final full suite: **128 tests passed**, with three existing non-fatal Streamlit/Pandas warnings. Ruff and the heuristic secret scan passed. Regression cases cover complete/incomplete comparison panels, optional technical JSON, exact identities, conflicts despite matching GTIN, the M510/M650 example, compatibility prose, title-only evidence, zero versus missing shipping, actionable next steps, provider normalizers, Amazon/Best Buy DOM fixtures, bootstrap safety and SQLite preservation.

Actual Chromium opened the new comparison expander against existing real research, rendered the evidence/logistics tables, kept technical details optional and reported no browser page errors. [Observed comparison panel](images/comparison-evidence.png).

Catalog pages may still omit detailed specifications. A fresh collection is needed to retain newly available metadata; historical records are not backfilled or rewritten. Title-code recognition is deliberately narrow, avoids compatibility prose and cannot replace manufacturer/variant verification. No universal unit conversion, new source access or authenticated API verification is claimed. Incomplete logistics and identity evidence continue to block profitability.
