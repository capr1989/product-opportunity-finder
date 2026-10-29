from dataclasses import replace
import json

import pytest
from streamlit.testing.v1 import AppTest

from pof.comparison import comparison_summary, profit_explanation
from pof.finance import Assumptions
from pof.matching import match
from pof.models import Product
from pof.opportunity_engine import DiscoverySettings, build_leads
from pof.storage import Store


def listings(complete=False):
    a = Product("Purchase", "Acme USB hub", role="supplier", price=27.99, url="https://example.com/buy")
    b = Product("Retail", "Acme USB hub", price=33.99, url="https://example.com/sell")
    if complete:
        fields = {"brand": "Acme", "model": "H100", "gtin": "0123456789012", "specs": {"material": "Aluminum", "pack": "1"},
                  "states": {"brand": "verified", "model": "verified", "gtin": "verified", "specs": "verified"}}
        a, b = replace(a, **fields, shipping=0, moq=1, availability="in_stock"), replace(b, **fields)
    return a, b


def test_missing_specs_and_profit_are_explained_without_mistaking_zero():
    a, b = listings()
    row = build_leads([a, b], DiscoverySettings())[0]
    summary = comparison_summary(a, b, row)
    assert summary["status"] == "Uncertain"
    assert any("purchase specifications" in m for m in summary["missing"])
    message = profit_explanation(row, summary)
    assert "inbound shipping is unknown" in message
    assert "product equivalence is not confirmed" in message
    assert row["observed_gap"] == pytest.approx(6)
    assert not row["financial"]["known"]
    a, b = listings(True)
    row = build_leads([a, b], DiscoverySettings(), Assumptions(advertising=0, platform_rate=0))[0]
    assert row["financial"]["known"]  # zero shipping is a known quote, not missing.
    summary = comparison_summary(a, b, row)
    assert summary["status"].startswith("Verified")
    assert "shipping is unknown" not in profit_explanation(row, summary)
    assert any("UPC / EAN / GTIN" in s for s in summary["support"])


def test_screenshot_models_are_contradicted_without_inventing_model_fields():
    a = Product("Amazon US", "Logitech M510 Full Size Ambidextrous 2.4 GHz Wireless Mouse", price=27.99,
                sku="B087Z5WDJ2", moq=1, condition="unknown")
    b = Product("Best Buy", "Logitech - Signature M650 L Full-size Wireless Optical Mouse", price=33.99,
                brand="Logitech", sku="6491142", condition="unknown")
    row = build_leads([a, b], DiscoverySettings())[0]
    summary = comparison_summary(a, b, row)
    assert summary["status"] == "Contradicted"
    assert "M510" in " ".join(summary["conflicts"]) and "M650" in " ".join(summary["conflicts"])
    assert row["state"] == "Rejected / Unattractive"
    assert not row["financial"]["known"]
    assert a.model == b.model == ""  # title clues have not become verified metadata.
    assert "exact product model" in summary["next_step"]


def test_title_units_never_establish_equivalence_and_matching_ids_do_not_hide_conflicts():
    a = Product("Purchase", "Acme USB drive 64 GB", brand="Acme")
    b = replace(a, source="Retail")
    assert match(a, b).kind == "unverified"
    a = replace(a, price=10, shipping=0, moq=1, availability="in_stock")
    b = replace(b, price=20)
    assert not build_leads([a, b], DiscoverySettings())[0]["financial"]["known"]
    a, b = listings(True)
    b = replace(b, specs={"material": "Plastic", "pack": "2"})
    row = build_leads([a, b], DiscoverySettings())[0]
    assert comparison_summary(a, b, row)["status"] == "Contradicted"
    assert not row["financial"]["known"]


@pytest.mark.parametrize("complete", [False, True])
def test_comparison_panel_renders_readable_evidence_and_optional_json(complete):
    script = '''
import streamlit as st
from pof.models import Product
from pof.opportunity_engine import build_leads, DiscoverySettings
from pof.comparison import comparison_summary
from pof.ui_comparison import comparison_panel
data = %r
a, b = [Product(**record) for record in data]
row = build_leads([a,b], DiscoverySettings())[0]
comparison_panel(a,b,row,comparison_summary(a,b,row))
''' % [p.record() for p in listings(complete)]
    app = AppTest.from_string(script, default_timeout=30).run()
    assert not app.exception
    assert any("Product equivalence:" in value.value for value in app.markdown)
    assert any(e.label == "Technical Details" for e in app.expander)
    assert app.table
    if not complete:
        assert any("inbound shipping is unknown" in value.value for value in app.markdown)


def test_explicit_source_attributes_survive_normalization_and_sqlite(tmp_path):
    from pof.extraction import parse_products
    record = {"@type": "Product", "name": "Source fixture", "brand": {"name": "Acme"}, "model": "H100",
              "sku": "source123", "gtin13": "0123456789012", "color": "Black",
              "width": {"value": 10, "unitText": "cm"},
              "additionalProperty": [{"name": "Material", "value": "Aluminum"}, {"name": "Package Quantity", "value": 2}],
              "offers": {"price": 20, "priceCurrency": "USD"}}
    raw = ('<script type="application/ld+json">' + json.dumps(record) + '</script>').encode()
    p = parse_products(raw, {"name": "Source", "role": "supplier", "url": "https://example.com/item"})[0]
    assert p.specs == {"material": "Aluminum", "pack": "2", "color": "Black", "width": "10 cm"}
    assert p.model == "H100" and p.gtin == "0123456789012"
    store = Store(tmp_path / "db.sqlite3")
    rid = store.add_run("Attribute round-trip", [p])
    assert store.products(rid)[0].record() == p.record()


def test_catalog_labels_are_explicit_and_bootstrap_variant_options_are_not_selected_specs():
    from pof.product_evidence import catalog_labels, explicit_fields
    fields = catalog_labels("Acme H100 from a title\nBrand: Acme\nModel:\nH100\nMaterial: Aluminum\nPackage quantity: 2")
    assert fields["model"] == "H100" and fields["specs"] == {"material": "Aluminum", "pack": "2"}
    assert not catalog_labels("Acme H100 USB hub, possibly black")["specs"]
    assert not explicit_fields({"skuProperties": [{"color": ["Black", "Blue"]}]})["specs"]


def test_provider_normalizers_preserve_available_attributes():
    from pof.live.bestbuy import BestBuyConnector
    from pof.live.public_catalogs import aliexpress_records
    bestbuy = BestBuyConnector.normalize({"sku": 123, "name": "Fixture", "url": "https://www.bestbuy.com/site/item/123.p",
        "manufacturer": "Acme", "modelNumber": "H100", "upc": "0123456789012",
        "details": [{"name": "Material", "value": "Aluminum"}]}, "US")
    assert bestbuy.brand == "Acme" and bestbuy.model == "H100" and bestbuy.specs["material"] == "Aluminum"
    record = {"productId": "123456", "title": {"displayTitle": "Fixture"}, "brandName": "Acme", "modelNumber": "H100",
              "specifications": {"material": "Aluminum"}, "prices": {"salePrice": {"minPrice": 10, "currencyCode": "USD"}}}
    script = 'window._dida_config_._init_data_= { data: ' + json.dumps({"products": [record]}) + ' };'
    product = aliexpress_records(script, "US", 1)[0]
    assert product.brand == "Acme" and product.specs["material"] == "Aluminum"
    assert product.source_attributes["price_basis"] == "advertised_minimum"


def test_model_compatibility_text_is_not_mistaken_for_a_product_model():
    a = Product("Purchase", "Acme M100 mouse", brand="Acme")
    b = Product("Retail", "Replacement cable for Acme M200 mouse", brand="Acme")
    from pof.matching import title_model_conflict
    assert not title_model_conflict(a, b)


def test_verified_identity_with_unknown_shipping_has_specific_next_step():
    a, b = listings(True)
    a = replace(a, shipping=None)
    row = build_leads([a, b], DiscoverySettings())[0]
    summary = comparison_summary(a, b, row)
    assert summary["next_step"].startswith("Confirm inbound shipping")
    assert "product equivalence is not confirmed" not in profit_explanation(row, summary)


def test_amazon_search_card_keeps_explicit_labels_when_available():
    from pof.live.bestbuy_browser import browser_installed
    from pof.live.public_catalogs import AmazonPublicConnector
    from pof.live.query import ResearchQuery
    if not browser_installed():
        pytest.skip("Optional Chromium not installed")

    class HTTP:
        def fetch(self, *args, **kwargs):
            return b'''<div class="s-main-slot"><div data-component-type="s-search-result" data-asin="B000000001">
                <h2>Acme H100 USB hub</h2><div class="a-price"><span class="a-offscreen">$27.99</span></div>
                <div>Brand: Acme</div><div>Model: H100</div><div>Material: Aluminum</div>
                <div>Package quantity: 2</div></div></div>'''

    p = AmazonPublicConnector(HTTP()).discover(ResearchQuery(limit=1, max_pages=1))[0]
    assert p.brand == "Acme" and p.model == "H100"
    assert p.specs == {"material": "Aluminum", "pack": "2"}
    assert p.gtin == "" and p.sku == "B000000001"
    assert p.state("specs") == "verified"
