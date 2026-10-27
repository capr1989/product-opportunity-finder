from types import SimpleNamespace

import pytest

from pof.demand import keyword_ideas
from pof.storage import Store


def test_official_keyword_request_schema_cache_and_missing_values(tmp_path, monkeypatch):
    from google.ads.googleads.client import GoogleAdsClient
    from google.oauth2.credentials import Credentials
    real = GoogleAdsClient(Credentials("not-a-real-token"), use_proto_plus=True)
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    metric = real.get_type("KeywordPlanHistoricalMetrics")
    metric.avg_monthly_searches = 1000
    metric.low_top_of_page_bid_micros = 500000
    item = SimpleNamespace(text="widget", keyword_idea_metrics=metric)
    calls = []

    class Service:
        def generate_keyword_ideas(self, request, timeout, retry):
            calls.append(request)
            assert list(request.keyword_seed.keywords) == ["widget"]
            assert request.geo_target_constants[0] == "geoTargetConstants/2840"
            assert request.language == "languageConstants/1000"
            assert request.page_size == 100
            assert retry is None
            return SimpleNamespace(raw_page=SimpleNamespace(results=[item]))

    client = SimpleNamespace(get_type=real.get_type, enums=real.enums, get_service=lambda name: Service())
    store = Store(tmp_path / "test.sqlite")
    rows, cached = keyword_ideas(store, ["widget"], client=client)
    assert not cached
    assert rows[0]["monthly_searches"] == 1000
    assert rows[0]["low_bid"] == 0.5
    assert rows[0]["high_bid"] is None
    assert rows[0]["cpc"] is None
    assert rows[0]["competition_index"] is None
    assert keyword_ideas(store, ["widget"], client=client)[1]
    assert len(calls) == 1


def test_google_exception_never_echoes_secret(tmp_path, monkeypatch):
    from google.ads.googleads.client import GoogleAdsClient
    from google.oauth2.credentials import Credentials
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    real = GoogleAdsClient(Credentials("not-a-real-token"), use_proto_plus=True)

    class Service:
        def generate_keyword_ideas(self, **kwargs):
            raise RuntimeError("SECRET_VALUE_MUST_NOT_LEAK")

    client = SimpleNamespace(get_type=real.get_type, enums=real.enums, get_service=lambda name: Service())
    with pytest.raises(ValueError) as error:
        keyword_ideas(Store(tmp_path / "test.sqlite"), ["widget"], client=client)
    assert "SECRET_VALUE" not in str(error.value)
    assert "Basic/Standard" in str(error.value)
