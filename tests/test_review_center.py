import csv
import io

from pof.models import Product


def test_shopify_export_is_draft_safe_and_does_not_copy_descriptions():
    from pof.shopify_export import shopify_export
    p = Product("Retailer", "=HYPERLINK(evil)", url="https://example.com/a", price=10,
                image_url="https://example.com/copyright.jpg", specs={"description": "Do not copy"})
    item = {"id": "a" * 64, "product": p, "rating": "Like", "note": "=formula"}
    data, preview, reports = shopify_export([item], {item["id"]: 19.99}, exclude_incomplete=False)
    row = next(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    assert row["Status"] == "draft"
    assert row["Published on online store"] == "false"
    assert row["Price"] == "19.99"
    assert row["Title"].startswith("'")
    assert not row["Description"]
    assert not row["Product image URL"]
    assert row["Option1 name"] == "Title" and row["Option1 value"] == "Default Title"
    assert reports[0]["warnings"]
    assert preview
    assert not shopify_export([item], {}, exclude_incomplete=False)[1]


def test_monthly_scenarios_never_invent_missing_profit():
    from pof.review_analysis import monthly_scenario
    assert monthly_scenario(20, None, 30) == {"monthly_revenue": 600, "monthly_contribution": None}
    assert monthly_scenario(20, 5, 30)["monthly_contribution"] == 150
