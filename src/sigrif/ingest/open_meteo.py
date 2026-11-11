from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from ..config import settings


class OpenMeteoError(RuntimeError):
    """Open-Meteo no respondió o entregó datos incompletos."""


@dataclass(frozen=True)
class WeatherReading:
    observed_at: datetime
    temperature: float
    humidity: float
    wind_kmh: float


def _parse_current(item: dict[str, Any]) -> WeatherReading:
    current = item.get("current") or {}
    try:
        observed = datetime.fromisoformat(str(current["time"])).replace(tzinfo=UTC)
        return WeatherReading(
            observed_at=observed,
            temperature=float(current["temperature_2m"]),
            humidity=float(current["relative_humidity_2m"]),
            wind_kmh=float(current["wind_speed_10m"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenMeteoError("Open-Meteo entregó una respuesta incompleta") from exc


def fetch_zones(
    zones: Sequence[tuple[int, float, float]],
    *,
    client: httpx.Client | None = None,
    url: str | None = None,
    timeout: float = 20.0,
) -> dict[int, WeatherReading]:
    if not zones:
        return {}
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    latitudes = ",".join(f"{lat:.5f}" for _, lat, _ in zones)
    longitudes = ",".join(f"{lon:.5f}" for _, _, lon in zones)
    try:
        response = http.get(
            url or settings.open_meteo_url,
            params={
                "latitude": latitudes,
                "longitude": longitudes,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
                "wind_speed_unit": "kmh",
                "timezone": "UTC",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload if isinstance(payload, list) else [payload]
        if len(items) != len(zones):
            raise OpenMeteoError("Open-Meteo no devolvió una respuesta por zona")
        return {
            zone_id: _parse_current(item)
            for (zone_id, _, _), item in zip(zones, items, strict=True)
        }
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        if isinstance(exc, OpenMeteoError):
            raise
        raise OpenMeteoError(f"No se pudo consultar Open-Meteo: {exc}") from exc
    finally:
        if owns_client:
            http.close()
