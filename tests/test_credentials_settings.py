import json

import pytest

from pof.credential_vault import CredentialVault, integration_credentials, masked_status
from pof.settings import get_settings, save_settings
from pof.storage import Store


def test_vault_scopes_masking_and_no_plaintext_fallback(monkeypatch):
    secret = "contract-credential-not-real"
    monkeypatch.setattr(CredentialVault, "load", lambda self, provider: {"BESTBUY_API_KEY": secret})
    assert integration_credentials("Best Buy")["BESTBUY_API_KEY"] == secret
    assert secret not in str(masked_status("Best Buy"))
    monkeypatch.setenv("BESTBUY_API_KEY", "environment-override")
    assert integration_credentials("Best Buy")["BESTBUY_API_KEY"] == "environment-override"
    with pytest.raises(ValueError):
        CredentialVault().save("CJdropshipping", {"key": secret})
    with pytest.raises(ValueError):
        CredentialVault().save("Best Buy", {"unknown": secret})


def test_connection_failures_do_not_persist_external_secrets(tmp_path, monkeypatch):
    from pof.ui_settings import test_integration as check_connection
    from pof.live.bestbuy import BestBuyConnector
    monkeypatch.setenv("BESTBUY_API_KEY", "contract-private-key")
    def fail(*args, **kwargs):
        raise ValueError("https://provider/?apiKey=contract-private-key")
    monkeypatch.setattr(BestBuyConnector, "discover", fail)
    store = Store(tmp_path / "test.sqlite3")
    result = check_connection(store, "Best Buy")
    assert result["status"] == "Test failed"
    assert "contract-private-key" not in json.dumps(store.get_config("integration_test", "Best Buy"))


def test_validated_settings_exclusions_and_cache(tmp_path):
    store = Store(tmp_path / "test.sqlite3")
    values = save_settings(store, {"market": "PA", "cache_seconds": 0, "categories": ["Audio"]})
    assert values["market"] == get_settings(store)["market"] == "PA"
    with pytest.raises(ValueError):
        save_settings(store, {"excluded_categories": ["Audio"]})
    with pytest.raises(ValueError):
        save_settings(store, {"BESTBUY_API_KEY": "never-store"})
    with pytest.raises(ValueError):
        save_settings(store, {"source_limit": 500})


def test_bestbuy_preference_does_not_require_key_for_browser():
    from pof.live.catalog import source_status
    row = source_status("Best Buy", {"bestbuy_method": "auto", "enabled": True}, {}, False)
    assert row["ready"]
    assert row["Collection method"] == "Live Scraping"
    row = source_status("Best Buy", {"bestbuy_method": "api-first", "enabled": True}, {}, True)
    assert row["Collection method"] == "Live API"
