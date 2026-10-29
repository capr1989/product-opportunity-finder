from dataclasses import replace

import pytest

from pof.models import Product
from pof.storage import Store
from pof.opportunity_engine import DiscoverySettings, build_leads, plan_searches, run_session


def pair():
    return [Product(source="AliExpress", role="supplier", title="USB C adapter hub", price=5,
                    url="https://www.aliexpress.com/item/1.html", currency="USD"),
            Product(source="Amazon US", title="USB Type C adapter hub", price=20,
                    url="https://www.amazon.com/dp/TEST", currency="USD")]


def test_diversified_plan_and_bounds():
    plan = plan_searches(DiscoverySettings(), {})
    assert len(plan) >= 3
    assert len({row["category"] for row in plan}) >= 3
    assert all(row["query"] for row in plan)
    assert plan_searches(DiscoverySettings(query_limit=1), {plan[0]["category"]: 10})[0] != plan[0]
    for kwargs in ({"query_limit": 99}, {"budget": float("nan")}, {"market": "xx"}):
        with pytest.raises(ValueError):
            DiscoverySettings(**kwargs)


def test_unknown_economics_remain_lead_and_gap_is_not_profit():
    row = build_leads(pair(), DiscoverySettings())[0]
    assert row["state"] == "Potential Lead"
    assert row["observed_gap"] == 15
    assert not row["financial"]["known"]
    assert "Confirm inbound shipping per unit" in row["missing"]


def test_currency_minimum_and_variant_conflict_cannot_become_profit():
    a, b = pair()
    a = replace(a, brand="Acme", model="H1", shipping=0, moq=1,
                source_attributes={"price_basis": "advertised_minimum"})
    b = replace(b, brand="Acme", model="H1")
    assert not build_leads([a, b], DiscoverySettings())[0]["financial"]["known"]
    a = replace(a, source_attributes={}, currency="PAB")
    row = build_leads([a, b], DiscoverySettings())[0]
    assert row["observed_gap"] is None
    assert not row["financial"]["known"]
    a = replace(a, currency="USD", specs={"pack": "2"})
    b = replace(b, specs={"pack": "4"})
    row = build_leads([a, b], DiscoverySettings())[0]
    assert row["state"] == "Rejected / Unattractive"


def test_budget_and_dropshipping_are_distinct():
    a, b = pair()
    a = replace(a, brand="Acme", model="H1", shipping=1, moq=10, availability="in_stock")
    b = replace(b, brand="Acme", model="H1")
    row = build_leads([a, b], DiscoverySettings(budget=20))[0]
    assert row["financial"]["known"]
    assert row["budget_feasible"] is False
    row = build_leads([a, b], DiscoverySettings(business_model="Dropshipping"))[0]
    assert not row["financial"]["known"]


def test_session_resume_cache_and_failure_isolation(tmp_path):
    store = Store(tmp_path / "research.db")
    calls = []

    def collect(query, names, db, credentials, **kwargs):
        calls.append(names[0])
        if names == ["Best Buy"]:
            raise RuntimeError("secret must not persist")
        run_id = db.add_run("contract", pair())
        return {"run_id": run_id, "reports": [{"source": names[0], "error": ""}]}

    settings = DiscoverySettings(query_limit=1, source_limit=3)
    result = run_session(store, settings, {}, collector=collect)
    assert result["status"] == "complete"
    assert result["leads"]
    assert "secret must not persist" not in str(result)
    count = len(calls)
    resumed = run_session(store, settings, {}, session_id=result["id"], collector=collect)
    assert len(calls) == count
    assert resumed["id"] == result["id"]
    assert store.products(demo=False)


def test_cancellation_and_demo_exclusion(tmp_path):
    store = Store(tmp_path / "research.db")
    result = run_session(store, DiscoverySettings(), {}, cancelled=lambda: True)
    assert result["status"] == "paused"
    assert result["completed"] == []
    assert not build_leads([replace(p, demo=True) for p in pair()], DiscoverySettings())


def test_deep_research_uses_seed_and_generates_followups(tmp_path):
    store = Store(tmp_path / "research.db")
    original = pair()[0]
    store.add_run("original evidence", [original])
    queries = []

    def collect(query, names, db, credentials, **kwargs):
        queries.append(query.keywords)
        return {"run_id": db.add_run("contract", pair()[1:]), "reports": []}

    result = run_session(store, DiscoverySettings(mode="Deep Research", query_limit=2, source_limit=1), {},
                         seeds=[original], collector=collect)
    assert result["leads"][0]["sell_id"] is not None
    assert result["plan"][0]["strategy"] == "supplier-first"
    assert queries == ["usb c adapter hub"]
    result = run_session(store, DiscoverySettings(mode="Deep Research", query_limit=2, source_limit=1), {}, collector=collect)
    assert len(result["plan"]) == 2
    assert result["plan"][1]["strategy"] == "retailer-first"


def test_expired_licensed_economics_are_not_retained_in_sessions(tmp_path):
    from datetime import datetime, timedelta, timezone
    store = Store(tmp_path / "research.db")
    a, b = pair()
    a = replace(a, source="Best Buy", collection_method="bestbuy_api", retention_hours=1,
                collected_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
    store.add_run("expired", [a, b])
    store.put_config("discovery_session", "test", {"leads": build_leads([a, b], DiscoverySettings())})
    store.purge_expired()
    assert store.get_config("discovery_session", "test")["leads"] == []


def test_access_barrier_does_not_trigger_more_queries(tmp_path):
    store = Store(tmp_path / "research.db")
    calls = []

    def collect(query, names, db, credentials, **kwargs):
        calls.append(1)
        return {"run_id": db.add_run("blocked", []), "reports": [
            {"source": names[0], "error": "challenge", "code": "access_barrier"}]}

    result = run_session(store, DiscoverySettings(query_limit=3, source_limit=1), {}, collector=collect)
    assert len(calls) == 1
    assert result["reports"][-1]["status"] == "skipped"


def test_external_attributes_are_search_data_not_code():
    from pof.opportunity_engine import followup_query
    product = replace(pair()[0], brand="Acme\n", model='H1; $(command) <script>alert(1)</script>')
    query = followup_query(product)
    assert query == "acme h1 command script alert 1 script"
    assert len(query) <= 180


def test_manual_approval_does_not_override_variant_conflict_or_minimum_cost():
    from pof.research import pair_id
    a, b = pair()
    a = replace(a, specs={"material": "plastic"}, shipping=0, moq=1, availability="in_stock")
    b = replace(b, specs={"material": "steel"})
    row = build_leads([a, b], DiscoverySettings(), reviews={pair_id(a, b): {"decision": "approve"}})[0]
    assert row["state"] == "Rejected / Unattractive"
    assert not row["financial"]["known"]
