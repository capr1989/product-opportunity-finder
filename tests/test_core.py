from dataclasses import replace

import pytest

from pof.finance import Assumptions, calculate
from pof.filters import evaluate
from pof.importing import import_csv
from pof.matching import match
from pof.models import Product
from pof.storage import Store


def test_finance_all_costs():
    result = calculate(10, 40, 2, 3, Assumptions())
    assert result["gross_profit"] == 28
    assert result["contribution_profit"] == 14.34
    assert result["break_even_cac"] == 19.34
    assert result["break_even_cpc"] == pytest.approx(0.3868)
    assert result["inventory_commitment"] == 36


def test_unknown_is_not_free_shipping():
    assert not calculate(10, 30, None, 1, Assumptions())["known"]
    assert not calculate(10, 30, 0, 1, Assumptions(), "EUR")["known"]


def test_snapshot_history(tmp_path):
    store = Store(tmp_path / "test.db")
    p = Product("test", "SSD 128 GB", price=10)
    first = store.add_run("one", [p])
    store.add_run("two", [replace(p, price=8)])
    assert store.products()[0].price == 8
    assert store.products(first)[0].price == 10
    assert len(store.price_history(p)) == 2


def test_csv_and_malformed():
    assert import_csv(b"source,title,price\nA,Widget,5\n")[0].price == 5
    for raw in (b"source,title,price\nA,Widget,NaN", b"source,title\nA", b"title\nWidget"):
        with pytest.raises(ValueError):
            import_csv(raw)


def test_variants_veto_gtin():
    p = Product("a", "Drive 128 GB", gtin="123", brand="Brand")
    assert match(p, replace(p, source="b", title="Drive 256 GB")).kind == "similar"
    assert match(p, replace(p, source="b")).kind == "exact"


def test_nested_filters_and_unknowns():
    group = {"logic": "OR", "rules": [
        {"field": "price", "op": "lte", "value": 5},
        {"logic": "AND", "rules": [{"field": "shipping", "op": "lte", "value": 2, "unknown": "include"}]}]}
    passed, warnings = evaluate({"price": 10}, group)
    assert passed and warnings == ["Unknown shipping"]
