"""Cliente HTTP entre la API pública y el servicio de inferencia."""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class IAUnavailable(RuntimeError):
    """El servicio de IA no respondió o devolvió un error recuperable."""


@dataclass
class CircuitBreaker:
    """Circuit breaker mínimo: cerrado, abierto y medio abierto.

    Cuenta fallos consecutivos de una llamada completa (incluidos sus
    reintentos). Al abrirse, rechaza solicitudes durante ``recovery_timeout``
    segundos y luego permite una única prueba de recuperación.
    """

    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    _failures: int = 0
    _opened_at: float | None = None
    _probe_in_flight: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def allow_request(self) -> bool:
        """Indica si se puede intentar una llamada."""

        with self._lock:
            if self._opened_at is None:
                return True
            if time.monotonic() - self._opened_at < self.recovery_timeout:
                return False
            if self._probe_in_flight:
                return False
            self._probe_in_flight = True
            return True

    def record_success(self) -> None:
        """Cierra el circuito tras una llamada exitosa."""

        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._probe_in_flight = False

    def record_failure(self) -> None:
        """Abre el circuito al superar el umbral de fallos."""

        with self._lock:
            self._probe_in_flight = False
            self._failures += 1
            if self._failures >= self.failure_threshold or self._opened_at is not None:
                self._opened_at = time.monotonic()

    def snapshot(self) -> dict[str, Any]:
        """Estado observable para pruebas y diagnóstico."""

        with self._lock:
            if self._opened_at is None:
                state = "closed"
            elif time.monotonic() - self._opened_at < self.recovery_timeout:
                state = "open"
            else:
                state = "half-open"
            return {"state": state, "failures": self._failures}

    def reset(self) -> None:
        """Vuelve al estado cerrado; útil para pruebas."""

        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._probe_in_flight = False


_BREAKER = CircuitBreaker()
_OCR_BREAKER = CircuitBreaker()


def reset_circuit_breaker() -> None:
    """Reinicia los circuitos globales entre ejecuciones de prueba."""

    _BREAKER.reset()
    _OCR_BREAKER.reset()


def predict_risk(
    features: Mapping[str, Any],
    client: httpx.Client | None = None,
    attempts: int = 3,
    request_id: str | None = None,
    breaker: CircuitBreaker | None = None,
) -> dict[str, Any]:
    """Solicita una predicción con reintentos, backoff y circuit breaker."""

    active_breaker = breaker or _BREAKER
    if not active_breaker.allow_request():
        raise IAUnavailable("Circuito de IA abierto; intenta nuevamente en unos segundos.")

    owns_client = client is None
    http_client = client or httpx.Client(base_url=settings.ia_url, timeout=5.0)
    headers = {"X-Request-ID": request_id} if request_id else {}
    last_error: Exception | None = None

    try:
        for attempt in range(attempts):
            try:
                response = http_client.post(
                    "/predict",
                    json=dict(features),
                    headers=headers,
                )
                response.raise_for_status()
                active_breaker.record_success()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    active_breaker.record_success()
                    raise IAUnavailable(
                        f"El servicio de IA rechazó la solicitud ({exc.response.status_code})"
                    ) from exc
                last_error = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc

            if attempt < attempts - 1:
                delay = (0.2 * (2**attempt)) + (secrets.randbelow(100) / 1000)
                time.sleep(delay)

        active_breaker.record_failure()
        logger.warning(
            "request_id=%s ia_unavailable state=%s",
            request_id or "sin-id",
            active_breaker.snapshot()["state"],
        )
        raise IAUnavailable("No se pudo contactar al servicio de IA") from last_error
    finally:
        if owns_client:
            http_client.close()


def ocr_image(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    client: httpx.Client | None = None,
    attempts: int = 2,
    request_id: str | None = None,
    breaker: CircuitBreaker | None = None,
) -> dict[str, Any]:
    """Envía una imagen al servicio IA con reintentos y circuito propio."""

    active_breaker = breaker or _OCR_BREAKER
    if not active_breaker.allow_request():
        raise IAUnavailable("Circuito de OCR abierto; intenta nuevamente en unos segundos.")

    owns_client = client is None
    http_client = client or httpx.Client(base_url=settings.ia_url, timeout=45.0)
    headers = {"X-Request-ID": request_id} if request_id else {}
    last_error: Exception | None = None

    try:
        for attempt in range(attempts):
            try:
                response = http_client.post(
                    "/ocr",
                    files={"file": (filename, image_bytes, content_type)},
                    headers=headers,
                )
                response.raise_for_status()
                active_breaker.record_success()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    active_breaker.record_success()
                    raise IAUnavailable(
                        f"El servicio de OCR rechazó la imagen ({exc.response.status_code})"
                    ) from exc
                last_error = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc

            if attempt < attempts - 1:
                delay = (0.3 * (2**attempt)) + (secrets.randbelow(100) / 1000)
                time.sleep(delay)

        active_breaker.record_failure()
        logger.warning(
            "request_id=%s ocr_unavailable state=%s",
            request_id or "sin-id",
            active_breaker.snapshot()["state"],
        )
        raise IAUnavailable("No se pudo contactar al servicio de OCR") from last_error
    finally:
        if owns_client:
            http_client.close()


def model_info(
    client: httpx.Client | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Obtiene la model card desde el servicio de IA (sin reintentos largos)."""

    owns_client = client is None
    http_client = client or httpx.Client(base_url=settings.ia_url, timeout=5.0)
    headers = {"X-Request-ID": request_id} if request_id else {}
    try:
        response = http_client.get("/model", headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise IAUnavailable("No se pudo leer la información del modelo") from exc
    finally:
        if owns_client:
            http_client.close()
