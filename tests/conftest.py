import pytest

from sigrif.config import settings


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
