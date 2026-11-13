from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..evaluation import evaluate_and_store
from ..events import publish_reading
from ..models import IngestionRun, Zone
from .dmc import DMCError, DMCStation, fetch_stations, interpolate_station
from .open_meteo import fetch_zones

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZoneWeather:
    zone_id: int
    source: str
    observed_at: datetime
    temperature: float
    humidity: float
    wind_kmh: float


def _zone_centroids(session: Session) -> list[tuple[Zone, float, float]]:
    rows = session.execute(
        select(
            Zone,
            func.ST_Y(func.ST_Centroid(Zone.geometry)),
            func.ST_X(func.ST_Centroid(Zone.geometry)),
        ).order_by(Zone.id)
    ).all()
    result: list[tuple[Zone, float, float]] = []
    for row in rows:
        result.append((cast(Zone, row[0]), float(row[1]), float(row[2])))
    return result


def _synthetic(zones: Sequence[tuple[Zone, float, float]]) -> list[ZoneWeather]:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    result = []
    for index, (zone, _, _) in enumerate(zones):
        wave = math.sin(index / 3)
        result.append(
            ZoneWeather(
                zone_id=zone.id,
                source="synthetic",
                observed_at=now,
                temperature=round(16 + 7 * wave, 2),
                humidity=round(62 - 12 * wave, 2),
                wind_kmh=round(12 + 4 * math.cos(index / 4), 2),
            )
        )
    return result


def _from_dmc(
    zones: Sequence[tuple[Zone, float, float]],
    stations: Sequence[DMCStation],
) -> tuple[list[ZoneWeather], list[int]]:
    readings: list[ZoneWeather] = []
    missing: list[int] = []
    for zone, latitude, longitude in zones:
        station = interpolate_station(latitude, longitude, stations, settings.ingest_station_radius_km)
        if station is None:
            missing.append(zone.id)
            continue
        readings.append(
            ZoneWeather(
                zone_id=zone.id,
                source="dmc",
                observed_at=station.observed_at,
                temperature=station.temperature,
                humidity=station.humidity,
                wind_kmh=station.wind_kmh,
            )
        )
    return readings, missing


def _direct_or_publish(session: Session, zone: Zone, weather: ZoneWeather) -> None:
    features = {
        "temperature": weather.temperature,
        "humidity": weather.humidity,
        "wind_speed": weather.wind_kmh,
        "vegetation": 0.3 if zone.vegetation is None else float(zone.vegetation),
        "historical_fires": 0 if zone.historical_fires is None else int(zone.historical_fires),
        "slope": 15.0 if zone.slope is None else float(zone.slope),
    }
    payload = {
        "zone_id": zone.id,
        **features,
        "source": weather.source,
        "observed_at": weather.observed_at.isoformat(),
    }
    if settings.messaging_enabled:
        publish_reading(payload)
    else:
        evaluate_and_store(
            session,
            zone,
            features,
            source=weather.source,
            observed_at=weather.observed_at,
            created_by="ingest",
        )


def run_ingestion(session: Session, provider: str | None = None) -> IngestionRun:
    """Ejecuta una pasada de ingesta y deja trazabilidad en ``ingestion_runs``."""

    selected = (provider or settings.ingest_provider or "auto").lower()
    started = datetime.now(UTC)
    run = IngestionRun(provider=selected, status="running", started_at=started)
    session.add(run)
    session.flush()

    zones = _zone_centroids(session)
    readings: list[ZoneWeather] = []
    notes: list[str] = []
    try:
        if selected == "synthetic":
            readings = _synthetic(zones)
            notes.append("proveedor sintético para pruebas")
        elif selected == "open_meteo":
            readings = [
                ZoneWeather(
                    zone_id,
                    "open_meteo",
                    item.observed_at,
                    item.temperature,
                    item.humidity,
                    item.wind_kmh,
                )
                for zone_id, item in fetch_zones(
                    [(z.id, lat, lon) for z, lat, lon in zones]
                ).items()
            ]
        else:
            try:
                stations = fetch_stations()
                readings, missing = _from_dmc(zones, stations)
                notes.append(f"dmc={len(readings)}")
                if selected == "auto" and missing:
                    missing_zones = [(z, lat, lon) for z, lat, lon in zones if z.id in missing]
                    fallback = fetch_zones([(z.id, lat, lon) for z, lat, lon in missing_zones])
                    readings.extend(
                        ZoneWeather(
                            zone_id,
                            "open_meteo",
                            item.observed_at,
                            item.temperature,
                            item.humidity,
                            item.wind_kmh,
                        )
                        for zone_id, item in fallback.items()
                    )
                    notes.append(f"open_meteo={len(fallback)}")
            except DMCError as exc:
                notes.append(f"dmc_error={exc}")
                if selected == "dmc":
                    raise
                fallback = fetch_zones([(z.id, lat, lon) for z, lat, lon in zones])
                readings = [
                    ZoneWeather(
                        zone_id,
                        "open_meteo",
                        item.observed_at,
                        item.temperature,
                        item.humidity,
                        item.wind_kmh,
                    )
                    for zone_id, item in fallback.items()
                ]
                notes.append(f"open_meteo={len(readings)}")

        zone_by_id = {zone.id: zone for zone, _, _ in zones}
        ok = 0
        failed = 0
        for weather in readings:
            zone = zone_by_id.get(weather.zone_id)
            if zone is None:
                failed += 1
                continue
            try:
                _direct_or_publish(session, zone, weather)
                ok += 1
            except Exception as exc:
                failed += 1
                logger.warning("ingesta falló para zona %s: %s", weather.zone_id, exc)

        run.zones_total = len(zones)
        run.zones_ok = ok
        run.zones_failed = max(failed, len(zones) - len(readings))
        run.status = "ok" if run.zones_failed == 0 else ("partial" if ok else "failed")
        run.message = "; ".join(notes)[:1000] or None
    except Exception as exc:
        run.status = "failed"
        run.zones_total = len(zones)
        run.zones_ok = 0
        run.zones_failed = len(zones)
        run.message = str(exc)[:1000]
        logger.exception("ingesta fallida")
    finally:
        finished = datetime.now(UTC)
        run.finished_at = finished
        run.duration_ms = int((finished - started).total_seconds() * 1000)
        session.commit()
        session.refresh(run)
    return run
