import pytest
from fastapi import HTTPException

from sigrif import auth
from sigrif.config import settings


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def test_auth_disabled_allows_local_operator(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
    user = auth.get_current_user(FakeRequest())
    assert user["sub"] == "local"
    assert "operadores" in user["cognito:groups"]


def test_missing_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(FakeRequest())
    assert exc.value.status_code == 401


def test_invalid_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)

    def reject(_):
        raise ValueError("bad token")

    monkeypatch.setattr(auth, "decode_token", reject)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(FakeRequest({"Authorization": "Bearer bad"}))
    assert exc.value.status_code == 401


def test_operator_group_is_allowed():
    user = {"cognito:groups": ["operadores"]}
    assert auth.require_operator(user) is user


def test_operator_group_is_required():
    with pytest.raises(HTTPException) as exc:
        auth.require_operator({"cognito:groups": ["usuarios"]})
    assert exc.value.status_code == 403
