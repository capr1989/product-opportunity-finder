from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


PAGES = ["Overview", "Product Search", "Broad Discovery", "Retail Deal Hunter", "Dropshipping Opportunities",
         "Product Comparison", "Google Ads Keyword Research", "Saved Products", "Research History",
         "Source Manager", "API Settings and Diagnostics", "Export Center"]


@pytest.mark.parametrize("page", PAGES)
def test_all_dashboard_pages(page):
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, [e.message for e in app.exception]


def test_demo_workflow_and_filters():
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.toggle[0].set_value(True).run()
    next(b for b in app.sidebar.button if b.label == "Load / reset demo snapshots").click().run()
    app.sidebar.radio[0].set_value("Dropshipping Opportunities").run()
    assert not app.exception
    assert len(app.dataframe) == 1
    app.sidebar.radio[0].set_value("Product Search").run()
    next(t for t in app.text_input if t.label.startswith("Product, model")).set_value("USB").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 3
    app.sidebar.radio[0].set_value("Retail Deal Hunter").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 4
