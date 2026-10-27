import json

from pof.live.query import ResearchQuery


def test_amazon_typed_public_search_has_no_api_key():
    from pof.live.public_catalogs import amazon_url
    assert "usb+hub" in amazon_url(ResearchQuery(keywords="usb hub"), 1)
    assert "apiKey" not in amazon_url(ResearchQuery(), 1)
    assert "electronics" in amazon_url(ResearchQuery(), 1)


def test_aliexpress_bootstrap_is_data_not_executable_code():
    from pof.live.public_catalogs import aliexpress_records
    record = {"productId": "123456", "title": {"displayTitle": "Test supplier fixture"},
              "prices": {"salePrice": {"currencyCode": "PAB", "minPrice": 5.12, "formattedPrice": "PAB 5.12"}}}
    source = 'window._dida_config_._init_data_= { data: ' + json.dumps({"products": [record]}) + ' }; throw Error("never executed");'
    rows = aliexpress_records(source, "PA", 5)
    assert len(rows) == 1
    assert rows[0].price == 5.12
    assert rows[0].currency == "PAB"
    assert rows[0].source_attributes["price_basis"] == "advertised_minimum"
    assert rows[0].shipping is None
    assert rows[0].role == "supplier"
