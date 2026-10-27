"""Read-only Google Ads keyword planning, environment OAuth and bounded caching."""
import csv
import hashlib
import io
import json
import os
import time

from pof.models import now
from pof.storage import Store

REQUIRED = ["GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_CUSTOMER_ID"]


def diagnostics() -> dict:
    missing = [key for key in REQUIRED if not os.environ.get(key)]
    return {"credentials_present": not missing, "missing_variables": missing,
        "authentication": "unverified — run a keyword request" if not missing else "requires credentials",
        "project_authorization": "unverified — controlled by OAuth credentials' Cloud project",
        "keyword_planning": "Basic/Standard access and permitted keyword-planning use may be required",
        "developer_token": "Sunset September 9, 2026; not proof of authorization"}


def google_client():
    from google.ads.googleads.client import GoogleAdsClient
    from google.oauth2.credentials import Credentials

    if not diagnostics()["credentials_present"]:
        raise ValueError("Missing environment credentials; see Diagnostics")
    credentials = Credentials(token=None, refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/adwords"])
    # Direct construction avoids older load_from_dict validation requiring a developer token.
    return GoogleAdsClient(credentials=credentials,
        developer_token=os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or None,
        login_customer_id=os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or None,
        use_proto_plus=True)


def keyword_ideas(store: Store, keywords: list[str], country: str = "2840", language: str = "1000",
                  interval: float = 2, cache_seconds: int = 86400, client=None) -> tuple[list[dict], bool]:
    if not 0.5 <= interval <= 60 or not 0 <= cache_seconds <= 604800:
        raise ValueError("Invalid rate/cache setting")
    if not 1 <= len(keywords) <= 20 or any(not k.strip() or len(k) > 200 for k in keywords):
        raise ValueError("Provide 1–20 keywords of at most 200 characters")
    if not country.isdigit() or not language.isdigit():
        raise ValueError("Country/language must be Google criterion IDs")
    customer = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")
    if not customer.isdigit() or len(customer) != 10:
        raise ValueError("Customer ID must have 10 digits, no dashes")
    key = "ads:" + hashlib.sha256(json.dumps([keywords, country, language, customer,
        os.environ.get("GOOGLE_ADS_CLIENT_ID", "")]).encode()).hexdigest()
    with store.connect() as db:
        cached = db.execute("SELECT payload,created FROM cache WHERE key=?", (key,)).fetchone()
        if cached and time.time() - cached[1] < cache_seconds:
            return json.loads(cached[0]), True
        last = db.execute("SELECT created FROM cache WHERE key='ads-rate'").fetchone()
        if last and time.time() - last[0] < interval:
            raise ValueError("Google Ads cooldown active")
        db.execute("INSERT OR REPLACE INTO cache VALUES('ads-rate','{}',?)", (time.time(),))
    client = client or google_client()
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer
    request.geo_target_constants.append(f"geoTargetConstants/{country}")
    request.language = f"languageConstants/{language}"
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request.keyword_seed.keywords.extend(keywords)
    request.page_size = 100
    try:
        response = client.get_service("KeywordPlanIdeaService").generate_keyword_ideas(
            request=request, timeout=30, retry=None)
        rows = []
        def metric_value(metric, field, divisor=1):
            return getattr(metric, field) / divisor if metric._pb.HasField(field) else None
        # One bounded page; do not let the pager automatically issue unlimited calls.
        for item in response.raw_page.results:
            metric = item.keyword_idea_metrics
            rows.append({"keyword": item.text, "monthly_searches": metric_value(metric, "avg_monthly_searches"),
                "competition": metric.competition.name, "competition_index": metric_value(metric, "competition_index"),
                "cpc": metric_value(metric, "average_cpc_micros", 1_000_000),
                "low_bid": metric_value(metric, "low_top_of_page_bid_micros", 1_000_000),
                "high_bid": metric_value(metric, "high_top_of_page_bid_micros", 1_000_000),
                "monthly_trends": [{"year": m.year, "month": m.month.name, "searches": m.monthly_searches}
                                   for m in metric.monthly_search_volumes],
                "country_criterion": country, "language_criterion": language,
                "bid_currency": "Google Ads account currency", "status": "verified",
                "origin": "Google Ads KeywordPlanIdeaService", "collected_at": now()})
    except Exception as exc:
        # Error codes alone provide useful diagnostics without echoing tokens/request metadata.
        failure = getattr(exc, "failure", None)
        codes = [str(e.error_code).strip().splitlines()[0] for e in failure.errors] if failure else []
        raise ValueError("Google Ads request failed. Check OAuth, customer access, Cloud project "
            "Basic/Standard access and keyword-planning permissible use. Codes: " + ", ".join(codes[:5])) from None
    with store.connect() as db:
        db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, json.dumps(rows), time.time()))
    return rows, False


def import_keywords(raw: bytes) -> list[dict]:
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("Keyword CSV exceeds 10 MiB")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or not {"keyword", "monthly_searches"}.issubset(reader.fieldnames):
        raise ValueError("Keyword CSV requires keyword,monthly_searches")
    rows = []
    for row in reader:
        if len(rows) >= 10000:
            raise ValueError("Too many keyword rows")
        if not row.get("keyword") or len(row["keyword"]) > 200:
            raise ValueError("Invalid keyword")
        data = {"keyword": row["keyword"], "status": "estimated", "origin": "User CSV",
                "collected_at": now()}
        for field in ("monthly_searches", "competition_index", "low_bid", "high_bid", "cpc"):
            if row.get(field):
                import math
                value = float(row[field])
                if not math.isfinite(value) or value < 0:
                    raise ValueError("Keyword metrics must be finite and non-negative")
                data[field] = value
        data.update({k: row[k] for k in ("trend", "competition", "seasonality", "bid_currency") if row.get(k)})
        rows.append(data)
    return rows
