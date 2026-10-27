"""Keep UI tests and their fixtures out of the user's real research database."""
import pytest


@pytest.fixture(autouse=True)
def isolated_app_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("POF_DATA_DIR", str(tmp_path / "app-data"))
