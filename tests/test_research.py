from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pof.demo import demo_products
from pof.finance import Assumptions
from pof.matching import match
from pof.research import deals, opportunities
from pof.scoring import DEFAULT_WEIGHTS, score


def test_fuzzy_title_without_identifiers_cannot_produce_profit():
    a, b = demo_products()[:2]
    a = replace(a, model="", gtin="", brand="", specs={})
    b = replace(b, model="", gtin="", brand="", specs={})
    rows = opportunities([a, b], Assumptions(), dropship=True)
    assert rows and not rows[0]["known"]
    assert rows[0]["match_kind"] == "unverified"


def test_capacity_bundle_and_brand_conflicts():
    a = demo_products()[0]
    for b in (replace(a, title="Demo USB-C Hub 128 GB"),):
        assert match(replace(a, title="Demo USB-C Hub 256 GB"), b).kind == "similar"
    assert match(a, replace(a, brand="Other")).kind == "similar"
    assert match(a, replace(a, specs={"variant": "other"})).kind == "similar"


def test_stale_quotes_are_not_deal_evidence():
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    products = [replace(p, collected_at=old) for p in demo_products()]
    assert products[0].state("price") == "stale"
    assert not deals(products)


def test_demo_real_data_never_match():
    a, b = demo_products()[:2]
    assert opportunities([a, replace(b, demo=False)], Assumptions()) == []


def test_weights_change_points_without_hard_filtering():
    p = demo_products()[0]
    weights = {k: 0 for k in DEFAULT_WEIGHTS}
    weights["match"] = 1
    value, factors = score(p, {"known": True}, 95, weights)
    assert value == 95
    assert factors["match"]["points"] == 95
