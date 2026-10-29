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
