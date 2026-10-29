from pathlib import Path

from streamlit.testing.v1 import AppTest

from pof.models import Product


def test_home_and_guided_do_not_need_keywords():
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    assert not app.exception
    assert app.sidebar.radio[0].value == "Automatic Discovery"
    assert any(t.value == "Find Products Worth Selling" for t in app.title)
    assert any(b.label == "Run Quick Scan" for b in app.button)
    assert not app.text_input
    app.sidebar.radio[0].set_value("Guided Research").run()
    assert not app.exception
    assert any(x.label == "Available investment (USD)" for x in app.number_input)
    assert any(x.label == "Selling market" for x in app.selectbox)
    app.sidebar.radio[0].set_value("Advanced Tools").run()
    assert any(b.label == "Source Manager" for b in app.button)


def test_scan_cards_save_and_deep_followup(monkeypatch):
    from pof import opportunity_engine

    def collect(query, names, store, credentials, **kwargs):
        products = [Product("AliExpress", "USB C hub", role="supplier", price=5,
                            url="https://www.aliexpress.com/item/contract.html"),
                    Product("Amazon US", "USB C hub adapter", price=25,
                            url="https://www.amazon.com/dp/CONTRACT00")]
        return {"run_id": store.add_run("ISOLATED UI CONTRACT", products),
                "reports": [{"source": names[0], "status": "test contract", "error": ""}]}

    monkeypatch.setattr(opportunity_engine, "run_research", collect)
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    next(b for b in app.button if b.label == "Run Quick Scan").click().run()
    assert not app.exception
    assert any(t.value == "USB C hub" for t in app.subheader)
    next(b for b in app.button if b.label == "Save opportunity").click().run()
    assert not app.exception
    next(b for b in app.button if b.label == "Investigate further").click().run()
    assert not app.exception
    assert next(r for r in app.radio if r.label == "Research depth").value == "Deep Research"
    next(b for b in app.button if b.label == "Run Deep Research").click().run()
    assert not app.exception
