from types import SimpleNamespace

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
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


def _private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _signed(private_key, claims):
    return pyjwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})


def _use_real_jwks(monkeypatch, private_key):
    configure_cognito(monkeypatch)
    key = SimpleNamespace(key=private_key.public_key())
    monkeypatch.setattr(
        auth,
        "_jwks_client",
        lambda: SimpleNamespace(get_signing_key_from_jwt=lambda _: key),
    )


def test_decode_real_access_token(monkeypatch):
    private_key = _private_key()
    _use_real_jwks(monkeypatch, private_key)
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/pool"
    token = _signed(
        private_key,
        {"token_use": "access", "client_id": "client", "iss": issuer, "sub": "u1"},
    )
    assert auth.decode_token(token)["sub"] == "u1"


def test_decode_real_id_token(monkeypatch):
    private_key = _private_key()
    _use_real_jwks(monkeypatch, private_key)
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/pool"
    token = _signed(
        private_key,
        {"token_use": "id", "aud": "client", "iss": issuer, "sub": "u1"},
    )
    assert auth.decode_token(token)["sub"] == "u1"


def test_decode_rejects_wrong_issuer(monkeypatch):
    private_key = _private_key()
    _use_real_jwks(monkeypatch, private_key)
    token = _signed(
        private_key,
        {
            "token_use": "access",
            "client_id": "client",
            "iss": "https://example.com",
            "sub": "u1",
        },
    )
    with pytest.raises(pyjwt.InvalidIssuerError):
        auth.decode_token(token)


def test_decode_rejects_wrong_access_client(monkeypatch):
    private_key = _private_key()
    _use_real_jwks(monkeypatch, private_key)
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/pool"
    token = _signed(
        private_key,
        {"token_use": "access", "client_id": "other", "iss": issuer, "sub": "u1"},
    )
    with pytest.raises(pyjwt.InvalidAudienceError):
        auth.decode_token(token)


def test_decode_rejects_wrong_id_audience(monkeypatch):
    private_key = _private_key()
    _use_real_jwks(monkeypatch, private_key)
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/pool"
    token = _signed(
        private_key,
        {"token_use": "id", "aud": "other", "iss": issuer, "sub": "u1"},
    )
    with pytest.raises(pyjwt.InvalidAudienceError):
        auth.decode_token(token)


class FakeKey:
    key = "public-key"


class FakeJwks:
    def get_signing_key_from_jwt(self, _):
        return FakeKey()


def configure_cognito(monkeypatch):
    monkeypatch.setattr(settings, "cognito_user_pool_id", "pool")
    monkeypatch.setattr(settings, "cognito_client_id", "client")
    monkeypatch.setattr(auth, "_jwks_client", lambda: FakeJwks())


def test_decode_access_token(monkeypatch):
    configure_cognito(monkeypatch)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {"token_use": "access", "client_id": "client"},
    )
    assert auth.decode_token("token")["token_use"] == "access"


def test_decode_id_token(monkeypatch):
    configure_cognito(monkeypatch)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {"token_use": "id", "aud": "client"},
    )
    assert auth.decode_token("token")["token_use"] == "id"


def test_decode_rejects_wrong_client(monkeypatch):
    configure_cognito(monkeypatch)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {"token_use": "access", "client_id": "otro"},
    )
    with pytest.raises(auth.jwt.InvalidAudienceError):
        auth.decode_token("token")
