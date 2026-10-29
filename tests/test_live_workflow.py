import json
from pathlib import Path
import socket

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from pof.live.catalog import source_status
from pof.live.discovery import run_research
from pof.live.query import ResearchQuery
from pof.security import SafeHTTP
from pof.storage import Store


def test_no_credentials_no_fallback_and_source_diagnostics(tmp_path, monkeypatch):
    from pof.live.bestbuy_browser import BestBuyBrowserConnector
    from pof.live.errors import SourceError
    def denied(self, query):
        raise SourceError("access_barrier", "Public page access is restricted; collection stopped")
    monkeypatch.setattr(BestBuyBrowserConnector, "discover", denied)
    store = Store(tmp_path / "test.db")
    result = run_research(ResearchQuery(), ["Best Buy", "Target"], store, {})
    assert result["products_found"] == 0
    assert not result["demo"]
    assert store.products() == []
    state = store.get_config("collection_state", "Best Buy")
    assert "restricted" in state["last_error"]
    assert not state.get("verified_live")
    row = source_status("Best Buy", store.get_config("source", "Best Buy"), state)
    assert row["Collection method"] == "Restricted"
    assert row["Verification"] == "Not live-verified"


def test_successful_contract_response_preserves_secret_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))])
    store = Store(tmp_path / "test.db")
    fixture = {"sku": 111, "name": "TEST CONTRACT DATA", "salePrice": 10,
               "url": "https://www.bestbuy.com/site/test/111.p", "onlineAvailability": True}
    http = SafeHTTP(0.5, httpx.MockTransport(lambda r: httpx.Response(200, json={"products": [fixture], "totalPages": 1})))
    progress = []
    result = run_research(ResearchQuery(limit=2), ["Best Buy"], store,
        {"BESTBUY_API_KEY": "private-contract-key"}, http=http, progress=lambda *args: progress.append(args))
    assert result["products_found"] == 1
    assert progress[-1][0] == 1
    assert store.products()[0].collection_method == "bestbuy_api"
    with store.connect() as db:
        config = db.execute("SELECT payload FROM config").fetchall()
        snapshots = db.execute("SELECT payload FROM snapshots").fetchall()
        caches = db.execute("SELECT payload FROM cache").fetchall()
    assert "private-contract-key" not in json.dumps([config, snapshots, caches])


@pytest.mark.parametrize("page", ["Setup", "New Research", "Research Results", "Help"])
def test_guided_pages_render(page):
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception


def test_first_time_setup_and_restricted_research_ux(monkeypatch):
    from pof.live.bestbuy_browser import BestBuyBrowserConnector
    from pof.live.errors import SourceError
    def denied(self, query):
        raise SourceError("access_barrier", "Public page access is restricted; collection stopped")
    monkeypatch.setattr(BestBuyBrowserConnector, "discover", denied)
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    assert app.sidebar.radio[0].value == "Automatic Discovery"
    app.sidebar.radio[0].set_value("Setup").run()
    next(b for b in app.button if b.label == "Skip setup for now").click().run()
    assert app.sidebar.radio[0].value == "Overview"
    next(b for b in app.sidebar.button if b.label == "Start New Research").click().run()
    assert app.sidebar.radio[0].value == "New Research"
    next(x for x in app.multiselect if x.label == "Sources").set_value(["Best Buy"]).run()
    next(b for b in app.button if b.label == "Run Research").click().run()
    assert not app.exception
    assert app.sidebar.radio[0].value == "Research Results"
    assert any("No live products" in i.value for i in app.info)
    assert any("restricted" in w.value for w in app.warning)
    assert not app.dataframe


def test_optional_api_key_form_is_masked_and_not_in_database(tmp_path, monkeypatch):
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Source Manager").run()
    next(x for x in app.selectbox if x.label == "Source connection").set_value("Best Buy").run()
    key_input = next(x for x in app.text_input if x.label == "Best Buy API key")
    assert key_input.proto.type == key_input.proto.PASSWORD
    key_input.set_value("private-ui-test-key")
    next(b for b in app.button if b.label == "Use key for this session").click().run()
    assert not app.exception
    db = Store(tmp_path / "app-data" / "research.sqlite3")
    assert "private-ui-test-key" not in json.dumps(db.configs("source"))


def test_run_results_save_export_flow_with_isolated_contract_data(monkeypatch):
    monkeypatch.setenv("BESTBUY_API_KEY", "contract-ui-key")
    def fetch(self, *args, **kwargs):
        return json.dumps({"products": [{"sku": 123, "name": "ISOLATED TEST PRODUCT", "salePrice": 20,
            "onlineAvailability": True, "condition": "New", "url": "https://www.bestbuy.com/site/test/123.p"}], "totalPages": 1}).encode()
    monkeypatch.setattr(SafeHTTP, "fetch", fetch)
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.radio[0].set_value("New Research").run()
    next(b for b in app.button if b.label == "Run Research").click().run()
    assert not app.exception
    assert app.sidebar.radio[0].value == "Research Results"
    assert app.dataframe[0].value.iloc[0]["Product"] == "ISOLATED TEST PRODUCT"
    assert len(app.get("download_button")) == 2
    next(b for b in app.button if b.label == "Save product").click().run()
    app.sidebar.radio[0].set_value("Saved Products").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 1
