"""Cliente HTTP entre la API pública y el servicio de inferencia."""

from __future__ import annotations

import secrets
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ..config import settings


class IAUnavailable(RuntimeError):
    """El servicio de IA no respondió o devolvió un error recuperable."""


def predict_risk(
    features: Mapping[str, Any],
    client: httpx.Client | None = None,
    attempts: int = 3,
) -> dict[str, Any]:
    """Solicita una predicción con reintentos y backoff exponencial simple."""

    owns_client = client is None
    http_client = client or httpx.Client(base_url=settings.ia_url, timeout=5.0)
    last_error: Exception | None = None

    try:
        for attempt in range(attempts):
            try:
                response = http_client.post("/predict", json=dict(features))
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise IAUnavailable(
                        f"El servicio de IA rechazó la solicitud ({exc.response.status_code})"
                    ) from exc
                last_error = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc

            if attempt < attempts - 1:
                delay = (0.2 * (2**attempt)) + (secrets.randbelow(100) / 1000)
                time.sleep(delay)

        raise IAUnavailable("No se pudo contactar al servicio de IA") from last_error
    finally:
        if owns_client:
            http_client.close()
