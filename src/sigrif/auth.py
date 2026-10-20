from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient

from .config import settings

ACCESS_USE = "access"
ID_USE = "id"
VALID_USES = {ACCESS_USE, ID_USE}


def _region() -> str:
    return settings.cognito_region or settings.aws_region


def _issuer() -> str:
    if not settings.cognito_user_pool_id:
        raise HTTPException(status_code=503, detail="Autenticación no configurada")
    return f"https://cognito-idp.{_region()}.amazonaws.com/{settings.cognito_user_pool_id}"


@lru_cache
def _jwks_client() -> PyJWKClient:
    if not settings.cognito_user_pool_id:
        raise HTTPException(status_code=503, detail="Autenticación no configurada")
    return PyJWKClient(f"{_issuer()}/.well-known/jwks.json", cache_keys=True)


def decode_token(token: str) -> dict[str, Any]:
    if not settings.cognito_client_id:
        raise HTTPException(status_code=503, detail="Autenticación no configurada")

    key = _jwks_client().get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        key.key,
        algorithms=["RS256"],
        issuer=_issuer(),
        options={"verify_aud": False},
    )

    token_use = payload.get("token_use")
    if token_use == ACCESS_USE and payload.get("client_id") != settings.cognito_client_id:
        raise jwt.InvalidAudienceError("client_id inválido")
    if token_use == ID_USE and payload.get("aud") != settings.cognito_client_id:
        raise jwt.InvalidAudienceError("aud inválido")
    if token_use not in VALID_USES:
        raise jwt.InvalidTokenError("token_use inválido")
    return payload


def get_current_user(request: Request) -> dict[str, Any]:
    if not settings.auth_enabled:
        return {"sub": "local", "cognito:groups": ["operadores"]}

    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Token requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return decode_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def require_operator(user: CurrentUser) -> dict[str, Any]:
    if "operadores" not in user.get("cognito:groups", []):
        raise HTTPException(status_code=403, detail="Se requiere el grupo operadores")
    return user


OperatorUser = Annotated[dict[str, Any], Depends(require_operator)]
