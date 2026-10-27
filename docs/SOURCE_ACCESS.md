# Source assessment — October 27, 2026

These findings are not a list of functional integrations. The user requested public-page collection without mandatory keys. Best Buy was live-verified first; Amazon and AliExpress were then implemented and live-verified. Remaining named adapters are not claimed as working. Terms restrictions are documented separately from technical failures. No CAPTCHA, login or anti-bot evasion is implemented.

| Source | Implementation | Findings |
|---|---|---|
| Best Buy | Live-verified public Playwright catalog; optional API contract-tested | Retrieved USD product offers in keyword and category runs. No API key used. |
| CJdropshipping | No working provider adapter | Both public-host probes redirected to a validation page. Stopped without bypass. Official API remains an optional credentialed route. |
| Amazon US | Live-verified public catalog/Playwright DOM adapter | Keyword run returned five USD-priced products; broad discovery returned three. Creators API remains an optional future route. |
| Walmart | No working provider adapter | Public probe redirected; product extraction is not verified. Marketplace API is a separate approved seller/partner route. |
| Target | No working provider adapter | Public HTML response received, but no product extraction has been verified. |
| eBay US | No working provider adapter | Public HTTP search probe returned 403. No bypass attempted. Official Browse API is a separate approved route. |
| Alibaba | No working provider adapter | Public search returned a challenge/verification document. No bypass attempted. |
| AliExpress | Live-verified public catalog/Playwright DOM adapter | Keyword run returned five supplier offers; broad discovery returned three. Returned currency PAB and minimum/coupon conditions are explicit; these are not confirmed unit costs. |
| Custom sources | Generic JSON/CSV/static-page and bounded browser-catalog infrastructure | Needs configuration and a genuine successful collection before verification. |

Official sources reviewed:

- Best Buy Products API: https://bestbuyapis.github.io/api-documentation/
- Optional key: https://developer.bestbuy.com/
- API retention: https://developers.bestbuy.com/legal
- Digital-agent terms: https://www.bestbuy.com/site/help-topics/terms-and-conditions/pcmcat204400050067.c?id=pcmcat204400050067
- CJ key: https://developers.cjdropshipping.com/en/api/start/apikey.html
- CJ Product List V2: https://developers.cjdropshipping.com/en/api/api2/api/product.html
- Amazon Creators API: https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction
- Walmart catalog: https://developer.walmart.com/us-marketplace/reference/getsearchresult
- Target terms: https://www.target.com/c/terms-conditions/-/N-4sr7l
- eBay Browse: https://developer.ebay.com/api-docs/buy/browse/overview.html
- eBay agreement: https://www.ebay.com/help/policies/member-behavior-policies/user-agreement?id=5414
- Developer portals: https://open.alibaba.com/ and https://open.aliexpress.com/

No third-party credential or sample product is used as live evidence.
