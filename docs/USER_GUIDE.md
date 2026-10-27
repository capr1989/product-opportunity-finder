# Live product research

## Setup

Launch with Launch.cmd. New users see Setup: choose USA, Panama or both, review source connections, set costs, then start a search. Optional integrations can be skipped. A target market is not evidence of shipping eligibility; Panama forwarding/import costs need confirmation.

Run InstallBrowser.cmd once for key-free collection. It downloads official Chromium to the ignored data/browsers folder without administrator privileges or global configuration changes. Keep Defender, firewall and sandboxing enabled. Website terms may restrict automated collection.

## Connect and research

1. Open Source Manager. **Best Buy, Amazon US and AliExpress have live-verified key-free collection.** Best Buy defaults to **Public browser — no API key** when no API key is configured; its official API is optional. Other listed providers are not working integrations merely because they are listed.
2. Click **Start New Research**. Choose dropshipping, deals, comparison, category exploration or a specific product.
3. Select sources and set price/category/optional keyword filters. Additional filters cover brand, model, seller, advertised sales, clearance, shipping, contribution margin and unknown values. Leave keywords blank for broad discovery.
4. Click **Run Research**. Progress shows source completion, product counts and elapsed time. Results open automatically. Each failed source explains its problem; no samples are substituted.
5. Inspect original listing links, observed prices, timestamps, evidence and missing information. Save products or export the current research to CSV/Excel.

The source table separates implemented adapters from live verification. A product-free page, configured key or parser test is not successful product discovery. Last successful collection is set only after actual records are returned. Best Buy public browsing may encounter location selection, changing markup, network failures or access barriers. These are reported as failures.

The optional API form masks the key and keeps it for the current browser session only. BESTBUY_API_KEY in the process environment is also supported. No key is required for browser mode. Never paste credentials in chat, CSV, URLs or Git.

## Understand results

Observed prices are not completed sales. Advertised regular prices/discounts are not independently verified bargains. Confirm delivery and stock on the source listing. Unknown shipping is not free shipping. Browser product cards may not provide GTIN, model or availability; those values remain unknown.

AliExpress currently returns some prices in PAB. The application preserves the reported currency and labels minimum/coupon offers explicitly. It does not convert PAB to USD or use a minimum offer as a confirmed unit cost. Price-range inputs use each source's displayed currency. Broad category searches use category hints where an exact taxonomy filter is unavailable; no specific product name is required.

Automatic comparisons start with the current run. Including previous verified data is explicit. Gross margin is the percentage after landed acquisition costs but before other variable expenses. Contribution profit additionally subtracts modeled fees, returns, advertising and fulfillment. Break-even CPC uses your conversion-rate estimate. Opportunity scores rank research priorities; they do not guarantee sales. Tooltips and expandable calculation details explain assumptions.

If a defensible match, second source or required cost is missing, the application shows missing information rather than invented profit. Product Comparison provides manual review. Hard filters exclude records; ranking preferences reorder them. Unknown values can be included with warnings or excluded.

## Save and export

Choose a product and click Save product. Open Saved Products to return to it. Research Results exports the current run; Export Center exports the library. Excel contains eight sheets including source references, assumptions and missing data. Best Buy API content has a 72-hour retention policy and is purged on startup/read after expiry. Downloaded files/backups remain your responsibility.

Help in the sidebar covers the main features and an interactive tutorial that makes no requests. Explicit Demo dataset mode provides a fictional sample session; live screens turn it off. Optional CSV imports remain in Advanced source configuration.

## Troubleshooting

- **Browser missing:** run InstallBrowser.cmd, then restart.
- **Public page did not load:** check connectivity or try later. No network/anti-bot evasion is attempted.
- **Country selection:** the browser uses the site's normal US selector/public US-store preference.
- **CAPTCHA/login/access denial:** collection stops without bypassing it.
- **No readable cards:** markup may have changed or need unsupported resources. This is not live verification.
- **Optional API key rejected:** check Source Manager or choose browser mode.
- **No comparisons:** collect equivalent products from a second working source and confirm required costs.
