# Google Ads read-only keyword research

As of the September 9, 2026 developer-token sunset, access levels belong to the Google Cloud project owning the OAuth credentials. A token is not proof that keyword planning is authorized. Official references:

- https://developers.google.com/google-ads/api/docs/api-policy/developer-token
- https://developers.google.com/google-ads/api/docs/api-policy/access-levels
- https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas
- https://developers.google.com/google-ads/api/docs/client-libs/python

1. In your existing Cloud project, enable Google Ads API and confirm access level/permissible use in the Google Ads API overview. Test/Explorer access does not imply keyword-planning access; apply for Basic/Standard where required. Your Ads customer/account must also permit your OAuth user access.
2. Configure an OAuth consent screen/client following Google's current installed-application OAuth procedure, and obtain a refresh token using Google's official client examples/tools. Keep credentials in the isolated VM. Do not paste them into chat, GitHub, source settings or CSV.
3. Set process environment variables before launching Streamlit. `.env.example` lists names only; it is not automatically loaded. In PowerShell use `$env:GOOGLE_ADS_CLIENT_ID = '<your value>'` and analogous variables. Avoid saving real values in scripts/shell history. Use a protected credential workflow approved for your VM where possible.
4. Required: `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID` (10 digits, no dashes). Optional `GOOGLE_ADS_LOGIN_CUSTOMER_ID` for manager access. `GOOGLE_ADS_PROJECT_ID` is informational; authorization actually follows the project owning the OAuth client. Legacy developer token is optional and ignored by post-sunset servers.
5. Start the application, open Diagnostics, then make a keyword request. Credential presence alone is reported as unverified. Only an actual successful request confirms the requested functionality. Failure messages explain OAuth/customer/project/access-level checks and expose error codes rather than raw token-bearing exceptions.

The pinned official google-ads client chooses its supported default API version. Review supported versions on upgrades; do not hardcode sunset API versions. Only `KeywordPlanIdeaService.generate_keyword_ideas` is exposed. The app requests at most one 100-result page per action, with no automatic pager traversal, retries disabled, configurable cooldown, and default 24-hour local cache. Diagnostics do not enumerate other account permissions or assert access from environment variables.

Results include historical average searches, monthly search volumes, competition/index, average CPC when returned, and low/high top-of-page bid estimates. Missing optional metrics remain unavailable rather than becoming zeros. Geo/language IDs default to US 2840 and English 1000. All monetary metrics use the Google Ads customer account currency and are not converted to USD. Bid ranges are not substituted for observed CPC. Monthly trend series are preserved for inspection/export; CSV can supply trend/seasonality labels. No automatic demand forecast is made.

CSV fallback requires `keyword,monthly_searches`; optional numeric fields `competition_index,cpc,low_bid,high_bid` and text fields `competition,trend,seasonality,bid_currency`. CSV metrics remain estimated. Associate a keyword with a product explicitly. Its keyword volumes do not prove monthly product sales. The application continues to work offline without any Google configuration.

Rotate by revoking old refresh tokens through Google, generating replacements and restarting the process with new environment values. API credentials are never added to GitHub Actions. No live authentication or project authorization has been verified without your credentials.
