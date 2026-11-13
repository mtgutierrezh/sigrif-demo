from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from ..config import settings

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class DMCError(RuntimeError):
    """La fuente DMC no respondió o no entregó datos utilizables."""


@dataclass(frozen=True)
class DMCStation:
    code: str
    name: str
    latitude: float
    longitude: float
    observed_at: datetime
    temperature: float
    humidity: float
    wind_kmh: float


def _number(value: Any) -> float | None:
    if value is None:
        return None
    match = NUMBER.search(str(value).replace(",", "."))
    return float(match.group()) if match else None


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_response(payload: dict[str, Any]) -> list[DMCStation]:
    stations: list[DMCStation] = []
    for item in payload.get("datosEstaciones", []):
        station = item.get("estacion") or {}
        try:
            latitude = float(station["latitud"])
            longitude = float(station["longitud"])
        except (KeyError, TypeError, ValueError):
            continue
        latest: DMCStation | None = None
        for reading in item.get("datos") or []:
            observed = _moment(reading.get("momento"))
            temperature = _number(reading.get("temperatura"))
            humidity = _number(reading.get("humedadRelativa"))
            wind_kt = _number(reading.get("fuerzaDelVientoPromedio10Minutos"))
            if observed is None or temperature is None or humidity is None:
                continue
            if not -10.0 <= temperature <= 50.0 or not 0.0 <= humidity <= 100.0:
                continue
            wind_kmh = round((wind_kt or 0.0) * 1.852, 2)
            if not 0.0 <= wind_kmh <= 150.0:
                continue
            candidate = DMCStation(
                code=str(station.get("codigoNacional", "")),
                name=str(station.get("nombreEstacion", "")),
                latitude=latitude,
                longitude=longitude,
                observed_at=observed,
                temperature=temperature,
                humidity=humidity,
                wind_kmh=wind_kmh,
            )
            if latest is None or candidate.observed_at > latest.observed_at:
                latest = candidate
        if latest is not None:
            stations.append(latest)
    if not stations:
        raise DMCError("DMC no entregó estaciones con temperatura y humedad válidas")
    return stations


def fetch_stations(
    *,
    client: httpx.Client | None = None,
    url: str | None = None,
    user: str | None = None,
    token: str | None = None,
    timeout: float = 20.0,
) -> list[DMCStation]:
    user = user or settings.dmc_user
    token = token or settings.dmc_token
    if not user or not token:
        raise DMCError("Faltan DMC_USER y DMC_TOKEN")
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.get(
            url or settings.dmc_url,
            params={"usuario": user, "token": token},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "Información recuperada":
            raise DMCError(f"DMC respondió: {payload.get('status', 'sin estado')}")
        return parse_response(payload)
    except (httpx.HTTPError, ValueError) as exc:
        raise DMCError(f"No se pudo consultar DMC: {exc}") from exc
    finally:
        if owns_client:
            http.close()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def nearest_station(
    latitude: float,
    longitude: float,
    stations: Sequence[DMCStation],
    radius_km: float,
) -> DMCStation | None:
    nearest = min(
        stations,
        key=lambda station: haversine_km(latitude, longitude, station.latitude, station.longitude),
        default=None,
    )
    if nearest is None:
        return None
    distance = haversine_km(latitude, longitude, nearest.latitude, nearest.longitude)
    return nearest if distance <= radius_km else None


def interpolate_station(
    latitude: float,
    longitude: float,
    stations: Sequence[DMCStation],
    radius_km: float,
    k: int = 3,
) -> DMCStation | None:
    """Interpola las k estaciones más cercanas con peso 1/d².

    La estación más cercana aporta la marca temporal. Así evitamos que todas
    las zonas cercanas hereden exactamente el mismo valor de una sola estación.
    """

    distances = sorted(
        (
            haversine_km(latitude, longitude, station.latitude, station.longitude),
            station,
        )
        for station in stations
    )
    nearby = [(distance, station) for distance, station in distances if distance <= radius_km][:k]
    if not nearby:
        return None
    nearest = nearby[0][1]
    weights = [1.0 / max(distance, 0.05) ** 2 for distance, _ in nearby]
    total = sum(weights)
    temperature = sum(weight * station.temperature for weight, (_, station) in zip(weights, nearby)) / total
    humidity = sum(weight * station.humidity for weight, (_, station) in zip(weights, nearby)) / total
    wind = sum(weight * station.wind_kmh for weight, (_, station) in zip(weights, nearby)) / total
    return DMCStation(
        code="idw",
        name=f"IDW {nearest.name}",
        latitude=latitude,
        longitude=longitude,
        observed_at=nearest.observed_at,
        temperature=round(temperature, 2),
        humidity=round(min(100.0, max(0.0, humidity)), 2),
        wind_kmh=round(max(0.0, wind), 2),
    )
