import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pof.models import Product
from pof.review_store import ReviewStore
from pof.storage import Store


def test_review_rate_favorites_export_and_notes():
    store = Store(Path(os.environ["POF_DATA_DIR"]) / "research.sqlite3")
    supplier = Product("Contract supplier", "CONTRACT USB hub", role="supplier", price=5,
                       brand="Contract", model="H1", shipping=1, moq=1, availability="in_stock",
                       url="https://example.com/supplier", states={"price": "verified"})
    retailer = Product("Contract retailer", "CONTRACT USB hub", price=25, brand="Contract", model="H1",
                       url="https://example.com/retailer")
    store.add_run("ISOLATED CONTRACT SCAN", [supplier, retailer])
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Product Review Center").run()
    assert not app.exception
    next(x for x in app.multiselect if x.label == "Product sources").set_value(["Contract supplier"]).run()
    next(x for x in app.text_area if x.label == "Personal notes").set_value("Verify packaging")
    next(b for b in app.button if b.label == "Love it").click().run()
    assert not app.exception
    assert ReviewStore(store).items(favorites=True)[0]["note"] == "Verify packaging"
    app.sidebar.radio[0].set_value("My Favorites").run()
    assert not app.exception
    next(c for c in app.checkbox if c.label == "Use all favorites").set_value(True).run()
    assert not app.exception
    assert len(app.get("download_button")) == 3
    next(c for c in app.checkbox if c.label == "Exclude products with incomplete verification").set_value(False).run()
    assert not app.exception
    assert any("1 included" in c.value for c in app.caption)
    next(b for b in app.button if b.label == "Maybe later").click().run()
    assert not ReviewStore(store).items(favorites=True)
    app.sidebar.radio[0].set_value("Maybe Later").run()
    assert not app.exception
    assert ReviewStore(store).items(watchlist=True)


def test_settings_masked_credentials_and_defaults(monkeypatch):
    from pof.credential_vault import CredentialVault
    memory = {}
    monkeypatch.setattr(CredentialVault, "load", lambda self, provider: memory.get(provider, {}))
    monkeypatch.setattr(CredentialVault, "save", lambda self, provider, values: memory.update({provider: values}))
    monkeypatch.setattr(CredentialVault, "remove", lambda self, provider: memory.pop(provider, None))
    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Settings").run()
    assert not app.exception
    field = next(x for x in app.text_input if x.label == "BESTBUY_API_KEY")
    assert field.proto.type == field.proto.PASSWORD
    field.set_value("isolated-contract-secret")
    next(b for b in app.button if b.label == "Save or replace credentials").click().run()
    assert not app.exception
    assert memory["Best Buy"]["BESTBUY_API_KEY"] == "isolated-contract-secret"
    store = Store(Path(os.environ["POF_DATA_DIR"]) / "research.sqlite3")
    assert "isolated-contract-secret" not in str(store.configs("settings"))
    next(b for b in app.button if b.label == "Remove saved credentials").click().run()
    assert not memory
