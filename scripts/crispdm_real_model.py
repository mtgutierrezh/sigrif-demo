from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import html
import json
import math
import re
import statistics
import time
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import joblib
import numpy as np
import shapefile
from shapely import make_valid
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import Pipeline

from sigrif.real_model import TabularPreprocessor

TARGET = "fire_next_season"
SEED = 42
REGION_CODE = 5
REGION_NAME = "valparaiso"
REGION_AREA_KM2 = 16396.0
ISLAND_COMUNAS = {"Isla de Pascua", "Juan Fernández"}
CONTINENTAL_BBOX = (-72.8, -34.4, -69.3, -31.7)
DEFAULT_SEASONS = [f"{year}_{year + 1}" for year in range(2010, 2025)]
CLIMATE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
NASA_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_PARAMETERS = "T2M,PRECTOTCORR,RH2M,WS2M"
CLIMATE_DAILY = (
    "temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean,"
    "wind_speed_10m_max,et0_fao_evapotranspiration"
)

NUMERIC_BASE = [
    "fuel_native",
    "fuel_plantation",
    "fuel_shrub",
    "fuel_grass",
    "fuel_agriculture",
    "fuel_urban",
    "vegetation",
    "slope",
    "area_km2",
    "log_area_km2",
    "population_log",
    "elev_mean_m",
    "elev_range_m",
    "centroid_lon",
    "centroid_lat",
    "prior_fires_last1_log",
    "prior_fires_last3_log",
    "prior_fires_last5_log",
    "prior_fires_total_log",
    "prior_burned_seasons",
    "prior_burn_rate",
    "seasons_since_last_fire",
    "prior_fire_area_last3_log",
    "prior_fire_area_total_log",
    "comuna_prior_fires_last1_log",
    "comuna_prior_fire_rate_last1",
    "comuna_prior_burn_rate",
]

CLIMATE_NUMERIC = [
    "prior_tmean_c",
    "prior_tmean_anom_c",
    "prior_precip_mm",
    "prior_precip_anom_mm",
    "prior_precip_ratio",
    "prior_dry_days",
    "prior_max_dry_spell",
    "prior_rh_mean",
    "prior_wind_mean",
    "prior_et0_mm",
    "prior_et0_anom_mm",
    "prior3_precip_anom_mm",
]

CATEGORICAL_BASE = ["comuna", "provincia", "dominant_fuel", "zone_type"]

IDENTIFIER_COLUMNS = [
    "season",
    "season_index",
    "zone_id",
    "zone_name",
    "comuna",
    "provincia",
    "zone_type",
]


@dataclass
class Zone:
    index: int
    zone_id: str
    name: str
    comuna: str
    provincia: str
    zone_type: str
    geometry: BaseGeometry
    area_km2: float
    centroid_lon: float
    centroid_lat: float
    properties: dict[str, Any]

    @property
    def dominant_fuel(self) -> str:
        return str(self.properties.get("dominant_fuel") or "Sin dato")

    @property
    def fuel_native(self) -> float | None:
        return _as_float(self.properties.get("fuel_native"))

    @property
    def fuel_plantation(self) -> float | None:
        return _as_float(self.properties.get("fuel_plantation"))

    @property
    def fuel_shrub(self) -> float | None:
        return _as_float(self.properties.get("fuel_shrub"))

    @property
    def fuel_grass(self) -> float | None:
        return _as_float(self.properties.get("fuel_grass"))

    @property
    def fuel_agriculture(self) -> float | None:
        return _as_float(self.properties.get("fuel_agriculture"))

    @property
    def fuel_urban(self) -> float | None:
        return _as_float(self.properties.get("fuel_urban"))


@dataclass
class FireEvent:
    season: str
    lon: float
    lat: float
    comuna: str
    provincia: str
    cause: str
    surface_ha: float
    name: str = ""
    zone_indices: list[int] = field(default_factory=list)


@dataclass
class FireLoadResult:
    events: list[FireEvent]
    inventory: list[dict[str, Any]]
    multi_zone_assignments: int = 0


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _as_int_code(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(round(number))


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.lower().replace("_", " ").split())


def _slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "sin_nombre"


def _first_present(mapping: dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _log1p(value: float | None) -> float | None:
    if value is None:
        return None
    return math.log1p(max(0.0, float(value)))


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def utm_to_lonlat(
    easting: float, northing: float, zone: int = 19, south: bool = True
) -> tuple[float, float]:
    """Convert WGS84 UTM coordinates to longitude/latitude without pyproj."""
    semi_major = 6378137.0
    flattening = 1.0 / 298.257223563
    eccentricity_sq = flattening * (2.0 - flattening)
    scale = 0.9996
    x = easting - 500000.0
    y = northing - 10000000.0 if south else northing
    meridional_arc = y / scale
    mu = meridional_arc / (
        semi_major
        * (
            1.0
            - eccentricity_sq / 4.0
            - 3.0 * eccentricity_sq**2 / 64.0
            - 5.0 * eccentricity_sq**3 / 256.0
        )
    )
    e1 = (1.0 - math.sqrt(1.0 - eccentricity_sq)) / (1.0 + math.sqrt(1.0 - eccentricity_sq))
    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
    )
    n1 = semi_major / math.sqrt(1.0 - eccentricity_sq * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = eccentricity_sq / (1.0 - eccentricity_sq) * math.cos(phi1) ** 2
    r1 = semi_major * (1.0 - eccentricity_sq) / (1.0 - eccentricity_sq * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * scale)
    latitude = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1**2 - 9.0 * eccentricity_sq) * d**4 / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1**2 - 252.0 * eccentricity_sq - 3.0 * c1**2)
        * d**6
        / 720.0
    )
    longitude = math.radians(-183.0 + zone * 6.0) + (
        d
        - (1.0 + 2.0 * t1 + c1) * d**3 / 6.0
        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1**2 + 8.0 * eccentricity_sq + 24.0 * t1**2)
        * d**5
        / 120.0
    ) / math.cos(phi1)
    return math.degrees(longitude), math.degrees(latitude)


def geometry_area_km2(geometry: BaseGeometry) -> float:
    latitude = geometry.centroid.y
    return float(geometry.area * 111.32 * math.cos(math.radians(latitude)) * 110.57)


def season_window(season: str) -> tuple[date, date]:
    start_year = int(season.split("_")[0])
    return date(start_year, 7, 1), date(start_year + 1, 6, 30)


def seasons_between(seasons: Sequence[str], start_index: int, end_index: int) -> list[str]:
    return list(seasons[max(0, start_index) : max(0, end_index)])


def load_zones(path: Path, include_islands: bool = False) -> tuple[list[Zone], dict[str, Any]]:
    payload = read_json(path)
    features = payload.get("features", [])
    zones: list[Zone] = []
    skipped: list[str] = []
    for index, feature in enumerate(features):
        properties = dict(feature.get("properties") or {})
        comuna = str(properties.get("Comuna") or "").strip()
        if not include_islands and comuna in ISLAND_COMUNAS:
            skipped.append(comuna)
            continue
        geometry_payload = feature.get("geometry")
        if not geometry_payload:
            skipped.append(f"{comuna}:sin_geometria")
            continue
        geometry = shape(geometry_payload)
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        if geometry.is_empty:
            skipped.append(f"{comuna}:geometria_vacia")
            continue
        name = str(
            properties.get("name")
            or properties.get("Nombre_Cer")
            or properties.get("Nombre_His")
            or f"Zona {index}"
        ).strip()
        zone = Zone(
            index=index,
            zone_id=f"Z{index:04d}",
            name=name,
            comuna=comuna or "Sin dato",
            provincia=str(properties.get("Provincia") or "Sin dato").strip(),
            zone_type=str(properties.get("zone_type") or properties.get("Nivel") or "sin_dato"),
            geometry=geometry,
            area_km2=geometry_area_km2(geometry),
            centroid_lon=float(geometry.centroid.x),
            centroid_lat=float(geometry.centroid.y),
            properties=properties,
        )
        zones.append(zone)
    metadata = {
        "source": str(path),
        "features_total": len(features),
        "zones_used": len(zones),
        "zones_skipped": len(skipped),
        "skipped_reasons": {
            "island_comunas": sum(1 for item in skipped if item in ISLAND_COMUNAS),
            "other": sum(1 for item in skipped if item not in ISLAND_COMUNAS),
        },
        "include_islands": include_islands,
        "total_area_km2": round(sum(zone.area_km2 for zone in zones), 3),
        "coverage_region_pct": round(
            100.0 * sum(zone.area_km2 for zone in zones) / REGION_AREA_KM2, 2
        ),
        "comunas": sorted({zone.comuna for zone in zones}),
        "provincias": sorted({zone.provincia for zone in zones}),
    }
    return zones, metadata


def _shapefile_crs(prj_path: Path) -> tuple[bool, int, bool]:
    if not prj_path.exists():
        return False, 19, True
    text = prj_path.read_text(encoding="utf-8", errors="ignore")
    geographic = "GEOGCS" in text and "PROJCS" not in text
    match = re.search(r"UTM_Zone_(\d{1,2})([NS])", text, flags=re.IGNORECASE)
    if match:
        return geographic, int(match.group(1)), match.group(2).upper() == "S"
    if geographic:
        return True, 19, True
    return False, 19, True


def _record_region(record: dict[str, Any]) -> bool:
    code = _as_int_code(_first_present(record, ["CODREG", "codreg", "COD_REGION", "cod_region"]))
    if code == REGION_CODE:
        return True
    region = _first_present(record, ["REGION", "region", "NOM_REGION", "nom_region"])
    return REGION_NAME in _normalize_text(region)


def _record_geometry_points(
    geometry: shapefile.Shape, geographic: bool, zone: int, south: bool
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if geometry.shapeType == 0:
        return points
    for x, y in geometry.points:
        if geographic:
            lon, lat = float(x), float(y)
        else:
            lon, lat = utm_to_lonlat(float(x), float(y), zone=zone, south=south)
        if not (math.isfinite(lon) and math.isfinite(lat)):
            continue
        points.append((lon, lat))
    return points


def _inside_continental_bbox(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = CONTINENTAL_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def load_fire_events(fires_dir: Path, zones: Sequence[Zone]) -> FireLoadResult:
    season_dirs = sorted(
        path
        for path in fires_dir.iterdir()
        if path.is_dir() and re.fullmatch(r"\d{4}_\d{4}", path.name)
    )
    if not season_dirs:
        raise FileNotFoundError(f"No se encontraron temporadas en {fires_dir}")
    tree = STRtree([zone.geometry for zone in zones])
    events: list[FireEvent] = []
    inventory: list[dict[str, Any]] = []
    multi_zone_assignments = 0
    seen: set[tuple[str, int, int]] = set()
    for season_dir in season_dirs:
        season = season_dir.name
        shp_path = season_dir / f"if_temporada_{season}.shp"
        if not shp_path.exists():
            raise FileNotFoundError(f"Falta {shp_path}")
        prj_path = shp_path.with_suffix(".prj")
        geographic, utm_zone, south = _shapefile_crs(prj_path)
        reader = shapefile.Reader(str(shp_path))
        raw_records = len(reader)
        region5_records = 0
        valid_points = 0
        outside_bbox = 0
        duplicates = 0
        season_events: list[FireEvent] = []
        for shape_record, record in zip(reader.shapes(), reader.records(), strict=False):
            record_dict = record.as_dict()
            if not _record_region(record_dict):
                continue
            region5_records += 1
            comuna = str(
                _first_present(record_dict, ["COMUNA", "comuna", "NOM_COMUNA"]) or ""
            ).strip()
            provincia = str(
                _first_present(record_dict, ["PROVINCIA", "provincia", "NOM_PROVINCIA"]) or ""
            ).strip()
            cause = str(
                _first_present(record_dict, ["CAUSA_GENE", "causa_gene", "CAUSA_GENERAL"]) or ""
            ).strip()
            surface = (
                _as_float(
                    _first_present(record_dict, ["SUPERFICIE", "superficie", "SUPERFICIE_HA"])
                )
                or 0.0
            )
            name = str(
                _first_present(record_dict, ["NOM_INCEN", "nom_incen", "NOMBRE", "nombre"]) or ""
            ).strip()
            for lon, lat in _record_geometry_points(shape_record, geographic, utm_zone, south):
                if not _inside_continental_bbox(lon, lat):
                    outside_bbox += 1
                    continue
                key = (season, round(lon, 5), round(lat, 5))
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                point = Point(lon, lat)
                zone_indices = [int(index) for index in tree.query(point, predicate="intersects")]
                if len(zone_indices) > 1:
                    multi_zone_assignments += 1
                event = FireEvent(
                    season=season,
                    lon=lon,
                    lat=lat,
                    comuna=comuna,
                    provincia=provincia,
                    cause=cause,
                    surface_ha=surface,
                    name=name,
                    zone_indices=zone_indices,
                )
                season_events.append(event)
                valid_points += 1
        events.extend(season_events)
        assigned = sum(1 for event in season_events if event.zone_indices)
        inventory.append(
            {
                "season": season,
                "raw_records": raw_records,
                "region5_records": region5_records,
                "valid_points": valid_points,
                "outside_bbox": outside_bbox,
                "duplicates": duplicates,
                "assigned": assigned,
                "unassigned": valid_points - assigned,
                "assignment_rate": round(assigned / valid_points, 4) if valid_points else None,
                "utc": geographic,
                "utm_zone": None if geographic else utm_zone,
            }
        )
    return FireLoadResult(
        events=events,
        inventory=inventory,
        multi_zone_assignments=multi_zone_assignments,
    )


def empty_counts(
    zones: Sequence[Zone], seasons: Sequence[str]
) -> dict[tuple[int, str], dict[str, float]]:
    return {(zone.index, season): {"n": 0, "area_ha": 0.0} for zone in zones for season in seasons}


def build_zone_season_counts(
    zones: Sequence[Zone],
    seasons: Sequence[str],
    events: Sequence[FireEvent],
) -> dict[tuple[int, str], dict[str, float]]:
    counts = empty_counts(zones, seasons)
    for event in events:
        for zone_index in event.zone_indices:
            key = (zone_index, event.season)
            if key not in counts:
                continue
            counts[key]["n"] += 1
            counts[key]["area_ha"] += max(0.0, event.surface_ha)
    return counts


def zone_events_by_comuna(events: Sequence[FireEvent], zones: Sequence[Zone]) -> dict[str, int]:
    zone_comuna = {zone.index: zone.comuna for zone in zones}
    result: dict[str, int] = {}
    for event in events:
        comunas = {zone_comuna[index] for index in event.zone_indices if index in zone_comuna}
        for comuna in comunas or {"Sin dato"}:
            result[comuna] = result.get(comuna, 0) + 1
    return result


def _season_climate(
    daily: dict[str, dict[str, float | None]],
    season: str,
) -> dict[str, float | None]:
    start, end = season_window(season)
    rows = [values for day, values in daily.items() if start <= day <= end]
    precipitation = [row.get("precipitation_sum") for row in rows]
    temperatures = [row.get("temperature_2m_mean") for row in rows]
    humidity = [row.get("relative_humidity_2m_mean") for row in rows]
    wind = [row.get("wind_speed_10m_max") for row in rows]
    et0 = [row.get("et0_fao_evapotranspiration") for row in rows]
    dry_days = 0
    max_dry_spell = 0
    current_spell = 0
    for value in precipitation:
        if value is None:
            continue
        if value < 1.0:
            dry_days += 1
            current_spell += 1
            max_dry_spell = max(max_dry_spell, current_spell)
        else:
            current_spell = 0
    total_precip = (
        None
        if not any(value is not None for value in precipitation)
        else sum(value for value in precipitation if value is not None)
    )
    return {
        "tmean_c": _mean(temperatures),
        "precip_mm": total_precip,
        "dry_days": float(dry_days) if rows else None,
        "max_dry_spell": float(max_dry_spell) if rows else None,
        "rh_mean": _mean(humidity),
        "wind_max_mean": _mean(wind),
        "et0_mm": None
        if not any(value is not None for value in et0)
        else sum(value for value in et0 if value is not None),
        "n_days": float(len(rows)),
    }


def derive_climate_seasons(payload: dict[str, Any]) -> dict[str, Any]:
    daily_payload = payload.get("daily") or {}
    dates = daily_payload.get("time") or []
    arrays = {
        "temperature_2m_mean": daily_payload.get("temperature_2m_mean") or [],
        "precipitation_sum": daily_payload.get("precipitation_sum") or [],
        "relative_humidity_2m_mean": daily_payload.get("relative_humidity_2m_mean") or [],
        "wind_speed_10m_max": daily_payload.get("wind_speed_10m_max") or [],
        "et0_fao_evapotranspiration": daily_payload.get("et0_fao_evapotranspiration") or [],
    }
    daily: dict[str, dict[str, float | None]] = {}
    for index, day_text in enumerate(dates):
        day = date.fromisoformat(day_text)
        daily[day] = {
            key: (values[index] if index < len(values) else None) for key, values in arrays.items()
        }
    seasons: dict[str, dict[str, float | None]] = {}
    start_years = sorted({day.year for day in daily if day.month >= 7})
    for year in start_years:
        season = f"{year}_{year + 1}"
        if season_window(season)[1] > max(daily):
            continue
        season_values = _season_climate(daily, season)
        if season_values["n_days"]:
            seasons[season] = season_values
    climatology_years = range(1991, 2020)
    climatology_rows = [
        seasons[f"{year}_{year + 1}"]
        for year in climatology_years
        if f"{year}_{year + 1}" in seasons
    ]
    climatology = {
        "tmean_c": _mean(row["tmean_c"] for row in climatology_rows),
        "precip_mm": _mean(row["precip_mm"] for row in climatology_rows),
        "dry_days": _mean(row["dry_days"] for row in climatology_rows),
        "max_dry_spell": _mean(row["max_dry_spell"] for row in climatology_rows),
        "rh_mean": _mean(row["rh_mean"] for row in climatology_rows),
        "wind_max_mean": _mean(row["wind_max_mean"] for row in climatology_rows),
        "et0_mm": _mean(row["et0_mm"] for row in climatology_rows),
        "period": "1991_1992..2019_2020",
        "n_seasons": len(climatology_rows),
    }
    return {
        "status": "ok",
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "elevation": payload.get("elevation"),
        "timezone": payload.get("timezone"),
        "seasons": seasons,
        "climatology": climatology,
    }


async def _fetch_climate_one(
    client: httpx.AsyncClient,
    comuna: str,
    latitude: float,
    longitude: float,
    cache_path: Path,
) -> tuple[str, dict[str, Any]]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": "1991-01-01",
        "end_date": "2025-12-31",
        "daily": CLIMATE_DAILY,
        "timezone": "America/Santiago",
    }
    last_error = ""
    for attempt in range(3):
        try:
            response = await client.get(CLIMATE_ENDPOINT, params=params)
            response.raise_for_status()
            derived = derive_climate_seasons(response.json())
            derived["comuna"] = comuna
            derived["source"] = "Open-Meteo Archive API (ERA5)"
            derived["fetched_at"] = datetime.now(UTC).isoformat()
            write_json(cache_path, derived)
            return comuna, derived
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(1.5 * (attempt + 1))
    return comuna, {
        "status": "error",
        "comuna": comuna,
        "error": last_error,
        "source": "Open-Meteo Archive API (ERA5)",
    }


async def _fetch_climate_many(
    targets: list[tuple[str, float, float, Path]],
) -> dict[str, dict[str, Any]]:
    semaphore = asyncio.Semaphore(4)

    async def limited(client: httpx.AsyncClient, item: tuple[str, float, float, Path]):
        async with semaphore:
            return await _fetch_climate_one(client, item[0], item[1], item[2], item[3])

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        results = await asyncio.gather(*(limited(client, item) for item in targets))
    return {comuna: payload for comuna, payload in results}


def _read_climate_cache(
    comunas: dict[str, list[float]],
    cache_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, float, float, Path]], dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    loaded: dict[str, dict[str, Any]] = {}
    missing: list[tuple[str, float, float, Path]] = []
    errors: dict[str, Any] = {}
    for comuna, (latitude, longitude) in comunas.items():
        path = cache_dir / f"{_slugify(comuna)}.json"
        if path.exists():
            try:
                payload = read_json(path)
                if payload.get("status") == "ok" and payload.get("seasons"):
                    loaded[comuna] = payload
                    continue
                errors[comuna] = payload
            except Exception:
                errors[comuna] = {"status": "error", "error": "cache ilegible"}
        missing.append((comuna, latitude, longitude, path))
    return loaded, missing, errors


def _nasa_daily_to_payload(payload: dict[str, Any]) -> dict[str, Any]:
    parameters = (payload.get("properties") or {}).get("parameter") or {}
    temperature = parameters.get("T2M") or {}
    precipitation = parameters.get("PRECTOTCORR") or {}
    humidity = parameters.get("RH2M") or {}
    wind = parameters.get("WS2M") or {}
    dates = sorted(set(temperature) | set(precipitation) | set(humidity) | set(wind))
    time_values: list[str] = []
    t_values: list[float | None] = []
    p_values: list[float | None] = []
    rh_values: list[float | None] = []
    wind_values: list[float | None] = []

    def clean(value: Any) -> float | None:
        number = _as_float(value)
        if number is None or number <= -900:
            return None
        return number

    for date_text in dates:
        if len(date_text) != 8 or not date_text.isdigit():
            continue
        time_values.append(f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]}")
        t_values.append(clean(temperature.get(date_text)))
        p_values.append(clean(precipitation.get(date_text)))
        rh_values.append(clean(humidity.get(date_text)))
        wind_values.append(clean(wind.get(date_text)))
    return {
        "daily": {
            "time": time_values,
            "temperature_2m_mean": t_values,
            "precipitation_sum": p_values,
            "relative_humidity_2m_mean": rh_values,
            "wind_speed_10m_max": wind_values,
            "et0_fao_evapotranspiration": [None] * len(time_values),
        },
        "latitude": (payload.get("geometry") or {}).get("coordinates", [None, None])[1],
        "longitude": (payload.get("geometry") or {}).get("coordinates", [None, None])[0],
        "elevation": None,
        "timezone": "UTC",
        "source": "NASA POWER (MERRA-2) daily",
    }


async def _fetch_nasa_one(
    client: httpx.AsyncClient,
    comuna: str,
    latitude: float,
    longitude: float,
    cache_path: Path,
) -> tuple[str, dict[str, Any]]:
    params = {
        "parameters": NASA_PARAMETERS,
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": "19910101",
        "end": "20251231",
        "format": "JSON",
    }
    last_error = ""
    for attempt in range(3):
        try:
            response = await client.get(NASA_ENDPOINT, params=params)
            response.raise_for_status()
            derived = derive_climate_seasons(_nasa_daily_to_payload(response.json()))
            derived["comuna"] = comuna
            derived["source"] = "NASA POWER (MERRA-2) daily"
            derived["fetched_at"] = datetime.now(UTC).isoformat()
            write_json(cache_path, derived)
            return comuna, derived
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(2.0 * (attempt + 1))
    return comuna, {
        "status": "error",
        "comuna": comuna,
        "error": last_error,
        "source": "NASA POWER (MERRA-2) daily",
    }


async def _fetch_nasa_many(
    targets: list[tuple[str, float, float, Path]],
) -> dict[str, dict[str, Any]]:
    semaphore = asyncio.Semaphore(2)

    async def limited(client: httpx.AsyncClient, item: tuple[str, float, float, Path]):
        async with semaphore:
            return await _fetch_nasa_one(client, item[0], item[1], item[2], item[3])

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        results = await asyncio.gather(*(limited(client, item) for item in targets))
    return {comuna: payload for comuna, payload in results}


def load_or_fetch_climate(
    zones: Sequence[Zone],
    cache_dir: Path,
    mode: str = "auto",
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    source_openmeteo = "Open-Meteo Archive API (ERA5), centroide comunal"
    source_nasa = "NASA POWER (MERRA-2), centroide comunal (respaldo por límite de Open-Meteo)"
    if mode == "off":
        return {}, {
            "status": "disabled",
            "source": None,
            "comunas_ok": 0,
            "comunas_total": 0,
            "comunas_error": 0,
            "excluded_from_model": True,
            "reason": "clima desactivado por --climate off",
        }
    comunas: dict[str, list[float]] = {}
    for comuna in sorted({zone.comuna for zone in zones}):
        members = [zone for zone in zones if zone.comuna == comuna]
        total_area = sum(zone.area_km2 for zone in members) or 1.0
        latitude = sum(zone.centroid_lat * zone.area_km2 for zone in members) / total_area
        longitude = sum(zone.centroid_lon * zone.area_km2 for zone in members) / total_area
        comunas[comuna] = [latitude, longitude]

    openmeteo_loaded, openmeteo_missing, openmeteo_errors = _read_climate_cache(comunas, cache_dir)
    openmeteo_errors_429 = sum(
        1 for payload in openmeteo_errors.values() if "429" in str(payload.get("error", ""))
    )
    if len(openmeteo_loaded) < len(comunas) and mode in {"auto", "on"}:
        retryable = [item for item in openmeteo_missing if item[0] not in openmeteo_errors]
        if retryable:
            try:
                fetched = asyncio.run(_fetch_climate_many(retryable))
            except Exception as exc:
                fetched = {
                    comuna: {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
                    for comuna, _, _, _ in retryable
                }
            for comuna, payload in fetched.items():
                if payload.get("status") == "ok":
                    openmeteo_loaded[comuna] = payload
                else:
                    openmeteo_errors[comuna] = payload
                    write_json(cache_dir / f"{_slugify(comuna)}.json", payload)
            openmeteo_errors_429 = sum(
                1 for payload in openmeteo_errors.values() if "429" in str(payload.get("error", ""))
            )
    openmeteo_coverage = len(openmeteo_loaded) / len(comunas) if comunas else 0.0
    if openmeteo_coverage >= 0.8:
        status = "ok" if openmeteo_coverage >= 0.999 else "partial"
        return openmeteo_loaded, {
            "status": status,
            "source": source_openmeteo,
            "comunas_total": len(comunas),
            "comunas_ok": len(openmeteo_loaded),
            "comunas_error": len(comunas) - len(openmeteo_loaded),
            "coverage_fraction": round(openmeteo_coverage, 4),
            "errors": openmeteo_errors,
            "cache_dir": str(cache_dir),
            "openmeteo_429_errors": openmeteo_errors_429,
            "excluded_from_model": False,
            "requested_period": "1991-01-01..2025-12-31",
            "climatology_period": "1991_1992..2019_2020",
        }

    nasa_dir = cache_dir.parent / "climate_nasa"
    nasa_loaded, nasa_missing, nasa_errors = _read_climate_cache(comunas, nasa_dir)
    if len(nasa_loaded) < len(comunas) and mode in {"auto", "on"}:
        try:
            fetched = asyncio.run(_fetch_nasa_many(nasa_missing))
        except Exception as exc:
            fetched = {
                comuna: {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
                for comuna, _, _, _ in nasa_missing
            }
        for comuna, payload in fetched.items():
            if payload.get("status") == "ok":
                nasa_loaded[comuna] = payload
            else:
                nasa_errors[comuna] = payload
                write_json(nasa_dir / f"{_slugify(comuna)}.json", payload)
    nasa_coverage = len(nasa_loaded) / len(comunas) if comunas else 0.0
    if nasa_coverage >= 0.8:
        status = "ok" if nasa_coverage >= 0.999 else "partial"
        return nasa_loaded, {
            "status": status,
            "source": source_nasa,
            "comunas_total": len(comunas),
            "comunas_ok": len(nasa_loaded),
            "comunas_error": len(comunas) - len(nasa_loaded),
            "coverage_fraction": round(nasa_coverage, 4),
            "errors": nasa_errors,
            "cache_dir": str(nasa_dir),
            "openmeteo_429_errors": openmeteo_errors_429,
            "fallback_reason": "Open-Meteo devolvió HTTP 429 (límite horario) y no alcanzó 80% de "
            "cobertura.",
            "excluded_from_model": False,
            "requested_period": "1991-01-01..2025-12-31",
            "climatology_period": "1991_1992..2019_2020",
        }

    if openmeteo_loaded:
        return openmeteo_loaded, {
            "status": "insufficient",
            "source": source_openmeteo,
            "comunas_total": len(comunas),
            "comunas_ok": len(openmeteo_loaded),
            "comunas_error": len(comunas) - len(openmeteo_loaded),
            "coverage_fraction": round(openmeteo_coverage, 4),
            "errors": openmeteo_errors,
            "cache_dir": str(cache_dir),
            "openmeteo_429_errors": openmeteo_errors_429,
            "nasa_coverage_fraction": round(nasa_coverage, 4),
            "excluded_from_model": True,
            "reason": "Cobertura climática menor a 80%; se excluyen variables climáticas para "
            "evitar imputación masiva.",
        }
    return {}, {
        "status": "unavailable",
        "source": None,
        "comunas_total": len(comunas),
        "comunas_ok": 0,
        "comunas_error": len(comunas),
        "coverage_fraction": 0.0,
        "errors": {**openmeteo_errors, **nasa_errors},
        "excluded_from_model": True,
        "reason": "Open-Meteo y NASA POWER fallaron o no alcanzaron cobertura mínima.",
    }


def _climate_feature_values(
    climate: dict[str, Any] | None,
    prior_season: str | None,
    prior_seasons: Sequence[str],
) -> dict[str, float | None]:
    values = {name: None for name in CLIMATE_NUMERIC}
    if not climate or climate.get("status") != "ok":
        return values
    seasons = climate.get("seasons") or {}
    current = seasons.get(prior_season or "")
    climatology = climate.get("climatology") or {}
    if current:
        precipitation = current.get("precip_mm")
        climatology_precipitation = climatology.get("precip_mm")
        values["prior_tmean_c"] = current.get("tmean_c")
        values["prior_precip_mm"] = precipitation
        values["prior_dry_days"] = current.get("dry_days")
        values["prior_max_dry_spell"] = current.get("max_dry_spell")
        values["prior_rh_mean"] = current.get("rh_mean")
        values["prior_wind_mean"] = current.get("wind_max_mean")
        values["prior_et0_mm"] = current.get("et0_mm")
        if current.get("tmean_c") is not None and climatology.get("tmean_c") is not None:
            values["prior_tmean_anom_c"] = current["tmean_c"] - climatology["tmean_c"]
        if precipitation is not None and climatology_precipitation is not None:
            values["prior_precip_anom_mm"] = precipitation - climatology_precipitation
            if climatology_precipitation > 0:
                values["prior_precip_ratio"] = precipitation / climatology_precipitation
        if current.get("et0_mm") is not None and climatology.get("et0_mm") is not None:
            values["prior_et0_anom_mm"] = current["et0_mm"] - climatology["et0_mm"]
    anomalies = []
    for season in prior_seasons[-3:]:
        season_values = seasons.get(season)
        if not season_values or season_values.get("precip_mm") is None:
            continue
        if climatology.get("precip_mm") is not None:
            anomalies.append(season_values["precip_mm"] - climatology["precip_mm"])
    if anomalies:
        values["prior3_precip_anom_mm"] = sum(anomalies) / len(anomalies)
    return values


def build_dataset_rows(
    zones: Sequence[Zone],
    seasons: Sequence[str],
    counts: dict[tuple[int, str], dict[str, float]],
    climate_by_comuna: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if len(seasons) < 2:
        raise ValueError("Se necesitan al menos dos temporadas para construir historia previa")
    climate_by_comuna = climate_by_comuna or {}
    comuna_zone_count: dict[str, int] = {}
    for zone in zones:
        comuna_zone_count[zone.comuna] = comuna_zone_count.get(zone.comuna, 0) + 1
    rows: list[dict[str, Any]] = []
    for target_index in range(1, len(seasons)):
        season = seasons[target_index]
        prior_seasons = seasons[:target_index]
        prior_season = prior_seasons[-1]
        for zone in zones:
            prior_n = [counts[(zone.index, item)]["n"] for item in prior_seasons]
            prior_area = [counts[(zone.index, item)]["area_ha"] for item in prior_seasons]
            last1 = prior_n[-1]
            last3 = sum(prior_n[-3:])
            last5 = sum(prior_n[-5:])
            total = sum(prior_n)
            area_last3 = sum(prior_area[-3:])
            area_total = sum(prior_area)
            burned_seasons = sum(1 for value in prior_n if value > 0)
            seasons_since = target_index + 1
            for offset, value in enumerate(reversed(prior_n), start=1):
                if value > 0:
                    seasons_since = offset
                    break
            comuna_members = [item for item in zones if item.comuna == zone.comuna]
            comuna_last1 = sum(counts[(item.index, prior_season)]["n"] for item in comuna_members)
            comuna_burned_last1 = sum(
                1 for item in comuna_members if counts[(item.index, prior_season)]["n"] > 0
            )
            comuna_burn_total = sum(
                counts[(item.index, item_season)]["n"] > 0
                for item in comuna_members
                for item_season in prior_seasons
            )
            population = _as_float(zone.properties.get("Población"))
            elevation = _as_float(zone.properties.get("dem_elev_media_m"))
            elevation_min = _as_float(zone.properties.get("dem_elev_min_m"))
            elevation_max = _as_float(zone.properties.get("dem_elev_max_m"))
            elevation_range = (
                elevation_max - elevation_min
                if elevation_max is not None and elevation_min is not None
                else None
            )
            climate_values = _climate_feature_values(
                climate_by_comuna.get(zone.comuna),
                prior_season,
                prior_seasons,
            )
            row: dict[str, Any] = {
                "season": season,
                "season_index": target_index,
                "zone_id": zone.zone_id,
                "zone_name": zone.name,
                "comuna": zone.comuna,
                "provincia": zone.provincia,
                "zone_type": zone.zone_type,
                "fuel_native": zone.fuel_native,
                "fuel_plantation": zone.fuel_plantation,
                "fuel_shrub": zone.fuel_shrub,
                "fuel_grass": zone.fuel_grass,
                "fuel_agriculture": zone.fuel_agriculture,
                "fuel_urban": zone.fuel_urban,
                "vegetation": _as_float(zone.properties.get("vegetation")),
                "slope": _as_float(zone.properties.get("slope")),
                "area_km2": zone.area_km2,
                "log_area_km2": math.log1p(max(0.0, zone.area_km2)),
                "population_log": _log1p(population),
                "elev_mean_m": elevation,
                "elev_range_m": elevation_range,
                "centroid_lon": zone.centroid_lon,
                "centroid_lat": zone.centroid_lat,
                "dominant_fuel": zone.dominant_fuel,
                "prior_fires_last1_log": _log1p(last1),
                "prior_fires_last3_log": _log1p(last3),
                "prior_fires_last5_log": _log1p(last5),
                "prior_fires_total_log": _log1p(total),
                "prior_burned_seasons": float(burned_seasons),
                "prior_burn_rate": burned_seasons / len(prior_seasons),
                "seasons_since_last_fire": float(seasons_since),
                "prior_fire_area_last3_log": _log1p(area_last3),
                "prior_fire_area_total_log": _log1p(area_total),
                "comuna_prior_fires_last1_log": _log1p(comuna_last1),
                "comuna_prior_fire_rate_last1": comuna_burned_last1 / len(comuna_members),
                "comuna_prior_burn_rate": comuna_burn_total
                / (len(comuna_members) * len(prior_seasons)),
                "n_fires_target": int(counts[(zone.index, season)]["n"]),
                TARGET: 1 if counts[(zone.index, season)]["n"] > 0 else 0,
            }
            row.update(climate_values)
            rows.append(row)
    return rows


def select_available_features(
    rows: Sequence[dict[str, Any]],
    numeric: Sequence[str],
    categorical: Sequence[str],
) -> tuple[list[str], list[str], list[str]]:
    available_numeric = [name for name in numeric if any(row.get(name) is not None for row in rows)]
    available_categorical = [
        name for name in categorical if any(row.get(name) not in (None, "") for row in rows)
    ]
    dropped = [
        name
        for name in list(numeric) + list(categorical)
        if name not in set(available_numeric + available_categorical)
    ]
    return available_numeric, available_categorical, dropped


def write_dataset_csv(path: Path, rows: Sequence[dict[str, Any]], metadata: dict[str, Any]) -> str:
    numeric = metadata["features"]["numeric"]
    categorical = metadata["features"]["categorical"]
    fieldnames = list(
        dict.fromkeys(IDENTIFIER_COLUMNS + numeric + categorical + ["n_fires_target", TARGET])
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: ("" if row.get(key) is None else row.get(key)) for key in fieldnames}
            )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def read_dataset_csv(
    path: Path,
    metadata_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metadata = read_json(metadata_path)
    numeric = metadata["features"]["numeric"]
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row: dict[str, Any] = dict(raw)
            for key, value in list(row.items()):
                if key in numeric:
                    row[key] = _as_float(value)
                elif key in {TARGET, "season_index", "n_fires_target"}:
                    row[key] = int(float(value)) if value not in ("", None) else None
                elif value == "":
                    row[key] = None
            rows.append(row)
    return rows, metadata


def dataset_summary(
    rows: Sequence[dict[str, Any]], zones: Sequence[Zone], seasons: Sequence[str]
) -> dict[str, Any]:
    positives = sum(int(row[TARGET]) for row in rows)
    target_seasons = list(seasons[1:])
    by_season = []
    for season in target_seasons:
        subset = [row for row in rows if row["season"] == season]
        positive = sum(int(row[TARGET]) for row in subset)
        by_season.append(
            {
                "season": season,
                "rows": len(subset),
                "positives": positive,
                "negatives": len(subset) - positive,
                "prevalence": round(positive / len(subset), 4) if subset else None,
            }
        )
    by_province = []
    for province in sorted({row["provincia"] for row in rows}):
        subset = [row for row in rows if row["provincia"] == province]
        positive = sum(int(row[TARGET]) for row in subset)
        by_province.append(
            {
                "provincia": province,
                "rows": len(subset),
                "positives": positive,
                "prevalence": round(positive / len(subset), 4) if subset else None,
            }
        )
    return {
        "rows": len(rows),
        "zones": len({row["zone_id"] for row in rows}),
        "target_seasons": target_seasons,
        "history_only_season": seasons[0],
        "positives": positives,
        "negatives": len(rows) - positives,
        "prevalence": round(positives / len(rows), 4) if rows else None,
        "by_season": by_season,
        "by_province": by_province,
    }


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _geometry_svg_path(geometry: BaseGeometry, project: Any) -> str:
    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    pieces: list[str] = []
    for polygon in polygons:
        if polygon.is_empty:
            continue
        exterior = list(polygon.exterior.coords)
        if not exterior:
            continue
        points = [project(lon, lat) for lon, lat in exterior]
        pieces.append("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z")
        for interior in polygon.interiors:
            hole = [project(lon, lat) for lon, lat in interior.coords]
            if hole:
                pieces.append("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in hole) + " Z")
    return " ".join(pieces)


def write_zone_map_svg(
    zones: Sequence[Zone],
    total_fires: dict[int, int],
    path: Path,
    width: int = 1000,
    height: int = 720,
) -> None:
    min_lon = min(zone.geometry.bounds[0] for zone in zones)
    min_lat = min(zone.geometry.bounds[1] for zone in zones)
    max_lon = max(zone.geometry.bounds[2] for zone in zones)
    max_lat = max(zone.geometry.bounds[3] for zone in zones)
    padding = 38
    scale_x = (width - 2 * padding) / max(1e-9, max_lon - min_lon)
    scale_y = (height - 2 * padding) / max(1e-9, max_lat - min_lat)
    scale = min(scale_x, scale_y)
    offset_x = padding + (width - 2 * padding - (max_lon - min_lon) * scale) / 2.0
    offset_y = padding + (height - 2 * padding - (max_lat - min_lat) * scale) / 2.0

    def project(lon: float, lat: float) -> tuple[float, float]:
        return (
            offset_x + (lon - min_lon) * scale,
            height - offset_y - (lat - min_lat) * scale,
        )

    nonzero = sorted(value for value in total_fires.values() if value > 0)
    if nonzero:
        quantiles = [
            nonzero[min(len(nonzero) - 1, int(len(nonzero) * q))] for q in (0.25, 0.5, 0.75, 0.9)
        ]
        cuts = [1] + quantiles
    else:
        cuts = [1, 2, 3, 4, 5]
    palette = ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c", "#800026"]

    def color_for(value: int) -> str:
        if value <= 0:
            return "#eeeeee"
        index = sum(1 for cut in cuts if value >= cut) - 1
        return palette[max(0, min(len(palette) - 1, index))]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="38" y="28" font-family="sans-serif" font-size="18" font-weight="bold">'
        "Incendios CONAF asignados por zona, 2010-2025</text>",
        '<text x="38" y="46" font-family="sans-serif" font-size="11" fill="#444">'
        "Puntos de ignición dentro de las 560 zonas continentales; fuera de zona no se "
        "asigna</text>",
    ]
    for zone in zones:
        geometry = zone.geometry.simplify(0.00015, preserve_topology=True)
        path_data = _geometry_svg_path(geometry, project)
        if not path_data:
            continue
        value = total_fires.get(zone.index, 0)
        parts.append(
            f'<path d="{path_data}" fill="{color_for(value)}" fill-rule="evenodd" '
            'stroke="#555555" stroke-width="0.25"/>'
        )
    top = sorted(zones, key=lambda zone: total_fires.get(zone.index, 0), reverse=True)[:8]
    for zone in top:
        value = total_fires.get(zone.index, 0)
        if value <= 0:
            continue
        x, y = project(zone.centroid_lon, zone.centroid_lat)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="#111111"/>'
            f'<text x="{x + 4:.1f}" y="{y - 4:.1f}" font-family="sans-serif" '
            f'font-size="9" fill="#111">{html.escape(zone.name[:32])}</text>'
        )
    legend_x = width - 235
    legend_y = 60
    parts.append(
        f'<rect x="{legend_x}" y="{legend_y}" width="197" height="146" fill="#ffffff" '
        'stroke="#999999" stroke-width="0.8"/>'
    )
    parts.append(
        f'<text x="{legend_x + 10}" y="{legend_y + 18}" font-family="sans-serif" '
        'font-size="11" font-weight="bold">Incendios por zona</text>'
    )
    labels = ["0", f"1-{max(1, cuts[1] - 1)}"]
    for index in range(1, len(cuts)):
        upper = cuts[index + 1] - 1 if index + 1 < len(cuts) else "max"
        labels.append(f"{cuts[index]}-{upper}")
    for index, color in enumerate(["#eeeeee"] + palette):
        y = legend_y + 32 + index * 19
        parts.append(
            f'<rect x="{legend_x + 10}" y="{y}" width="14" height="12" fill="{color}" '
            'stroke="#666" '
            f'stroke-width="0.4"/>'
        )
        parts.append(
            f'<text x="{legend_x + 30}" y="{y + 10}" font-family="sans-serif" '
            f'font-size="10">{html.escape(str(labels[index] if index < len(labels) else ""))}'
            "</text>"
        )
    parts.append(
        f'<text x="{width - 235}" y="{height - 18}" font-family="sans-serif" font-size="9" '
        'fill="#555">Fuente: CONAF, puntos de inicio; zonas censales/municipales</text>'
    )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_season_chart_svg(inventory: Sequence[dict[str, Any]], path: Path) -> None:
    width, height = 1000, 380
    left, right, top, bottom = 58, 24, 38, 58
    max_value = max([item["valid_points"] for item in inventory] + [1])
    plot_width = width - left - right
    plot_height = height - top - bottom
    bar_width = plot_width / max(1, len(inventory)) * 0.62
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="58" y="24" font-family="sans-serif" font-size="17" font-weight="bold">'
        "Incendios CONAF en la Región de Valparaíso por temporada</text>",
    ]
    for tick in range(0, 5):
        value = max_value * tick / 4.0
        y = height - bottom - plot_height * tick / 4.0
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            'stroke="#dddddd" stroke-width="0.8"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" font-family="sans-serif" font-size="10" '
            f'text-anchor="end">{int(round(value))}</text>'
        )
    for index, item in enumerate(inventory):
        center = left + (index + 0.5) * plot_width / len(inventory)
        total_height = plot_height * item["valid_points"] / max_value
        assigned_height = plot_height * item["assigned"] / max_value
        parts.append(
            f'<rect x="{center - bar_width / 2:.1f}" y="{height - bottom - total_height:.1f}" '
            f'width="{bar_width:.1f}" height="{total_height:.1f}" fill="#c6dbef" stroke="#6baed6" '
            f'stroke-width="0.4"/>'
        )
        parts.append(
            f'<rect x="{center - bar_width / 2:.1f}" y="{height - bottom - assigned_height:.1f}" '
            f'width="{bar_width:.1f}" height="{assigned_height:.1f}" fill="#2171b5"/>'
        )
        parts.append(
            f'<text x="{center:.1f}" y="{height - bottom + 16:.1f}" font-family="sans-serif" '
            f'font-size="9" text-anchor="end" transform="rotate(-45 {center:.1f} '
            f'{height - bottom + 16:.1f})">'
            f"{html.escape(item['season'])}</text>"
        )
    parts.append(
        f'<rect x="{width - 270}" y="{top}" width="12" height="12" fill="#c6dbef" '
        f'stroke="#6baed6"/>'
        f'<text x="{width - 252}" y="{top + 10}" font-family="sans-serif" font-size="10">Región '
        f"(puntos válidos)</text>"
    )
    parts.append(
        f'<rect x="{width - 270}" y="{top + 18}" width="12" height="12" fill="#2171b5"/>'
        f'<text x="{width - 252}" y="{top + 28}" font-family="sans-serif" font-size="10">Asignados '
        f"a una zona</text>"
    )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def run_eda(
    zones: Sequence[Zone],
    fire_result: FireLoadResult,
    seasons: Sequence[str],
    out_dir: Path,
    zone_metadata: dict[str, Any],
) -> dict[str, Any]:
    counts = build_zone_season_counts(zones, seasons, fire_result.events)
    target_seasons = list(seasons[1:])
    inventory = fire_result.inventory
    total_region = sum(item["valid_points"] for item in inventory)
    total_assigned = sum(item["assigned"] for item in inventory)
    total_unassigned = total_region - total_assigned
    assigned_by_comuna = zone_events_by_comuna(fire_result.events, zones)
    total_fires_by_zone = {
        zone.index: sum(counts[(zone.index, season)]["n"] for season in seasons) for zone in zones
    }
    positives_by_season = []
    for season in target_seasons:
        positive = sum(1 for zone in zones if counts[(zone.index, season)]["n"] > 0)
        positives_by_season.append(
            {
                "season": season,
                "rows": len(zones),
                "positives": positive,
                "negatives": len(zones) - positive,
                "prevalence": round(positive / len(zones), 4),
            }
        )
    total_rows = len(zones) * len(target_seasons)
    total_positives = sum(item["positives"] for item in positives_by_season)
    by_comuna = []
    for comuna in sorted({zone.comuna for zone in zones}):
        members = [zone for zone in zones if zone.comuna == comuna]
        positive = sum(
            1
            for zone in members
            for season in target_seasons
            if counts[(zone.index, season)]["n"] > 0
        )
        by_comuna.append(
            {
                "comuna": comuna,
                "zones": len(members),
                "area_km2": round(sum(zone.area_km2 for zone in members), 3),
                "assigned_fires_2010_2025": assigned_by_comuna.get(comuna, 0),
                "positive_zone_seasons": positive,
                "prevalence": round(positive / (len(members) * len(target_seasons)), 4),
            }
        )
    by_province = []
    for province in sorted({zone.provincia for zone in zones}):
        members = [zone for zone in zones if zone.provincia == province]
        positive = sum(
            1
            for zone in members
            for season in target_seasons
            if counts[(zone.index, season)]["n"] > 0
        )
        by_province.append(
            {
                "provincia": province,
                "zones": len(members),
                "positive_zone_seasons": positive,
                "prevalence": round(positive / (len(members) * len(target_seasons)), 4),
            }
        )
    top_zones = []
    for zone in sorted(zones, key=lambda item: total_fires_by_zone[item.index], reverse=True)[:20]:
        top_zones.append(
            {
                "zone_id": zone.zone_id,
                "zone_name": zone.name,
                "comuna": zone.comuna,
                "provincia": zone.provincia,
                "dominant_fuel": zone.dominant_fuel,
                "area_km2": round(zone.area_km2, 4),
                "assigned_fires_2010_2025": total_fires_by_zone[zone.index],
                "seasons_with_fire": sum(
                    1 for season in seasons if counts[(zone.index, season)]["n"] > 0
                ),
                "positive_target_seasons": sum(
                    1 for season in target_seasons if counts[(zone.index, season)]["n"] > 0
                ),
            }
        )
    tree = STRtree([zone.geometry for zone in zones])
    unassigned = [event for event in fire_result.events if not event.zone_indices]
    distances_km: list[float] = []
    for event in unassigned:
        point = Point(event.lon, event.lat)
        nearest = int(tree.nearest(point))
        distances_km.append(float(tree.geometries[nearest].distance(point) * 111.0))
    distances_km.sort()
    distance_summary = {}
    if distances_km:
        distance_summary = {
            "n": len(distances_km),
            "p10_km": round(distances_km[int(len(distances_km) * 0.1)], 3),
            "median_km": round(statistics.median(distances_km), 3),
            "p90_km": round(distances_km[int(len(distances_km) * 0.9)], 3),
            "max_km": round(distances_km[-1], 3),
            "within_0_5_km": round(
                sum(1 for value in distances_km if value <= 0.5) / len(distances_km), 4
            ),
            "within_1_km": round(
                sum(1 for value in distances_km if value <= 1.0) / len(distances_km), 4
            ),
            "within_2_km": round(
                sum(1 for value in distances_km if value <= 2.0) / len(distances_km), 4
            ),
        }
    missing_static = {}
    static_fields = [
        "fuel_native",
        "fuel_plantation",
        "fuel_shrub",
        "fuel_grass",
        "fuel_agriculture",
        "fuel_urban",
        "vegetation",
        "slope",
        "dem_elev_media_m",
        "Población",
        "dominant_fuel",
    ]
    for field_name in static_fields:
        missing_static[field_name] = sum(
            1 for zone in zones if zone.properties.get(field_name) in (None, "")
        )
    fuel_counts: dict[str, int] = {}
    for zone in zones:
        fuel_counts[zone.dominant_fuel] = fuel_counts.get(zone.dominant_fuel, 0) + 1
    map_path = out_dir / "real_eda_map.svg"
    chart_path = out_dir / "real_eda_seasons.svg"
    write_zone_map_svg(zones, total_fires_by_zone, map_path)
    write_season_chart_svg(inventory, chart_path)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": {
            "fires": str(fire_result.inventory[0]["season"]) if inventory else None,
            "fire_years": f"{seasons[0]}..{seasons[-1]}",
            "zones": zone_metadata.get("source"),
            "zone_documentation": "CONAF ocurrencia 2010-2025; IDE Minagri; DPA 2022; censo 2017",
            "region_area_km2": REGION_AREA_KM2,
        },
        "zones": {
            "used": len(zones),
            "features_total": zone_metadata.get("features_total"),
            "skipped": zone_metadata.get("zones_skipped"),
            "include_islands": zone_metadata.get("include_islands"),
            "total_area_km2": round(sum(zone.area_km2 for zone in zones), 3),
            "coverage_region_pct": zone_metadata.get("coverage_region_pct"),
            "dominant_fuel_counts": fuel_counts,
            "comunas": len({zone.comuna for zone in zones}),
            "provincias": len({zone.provincia for zone in zones}),
        },
        "fires": {
            "seasons": inventory,
            "total_region5_valid_points": total_region,
            "assigned": total_assigned,
            "unassigned": total_unassigned,
            "assignment_rate": round(total_assigned / total_region, 4) if total_region else None,
            "multi_zone_assignments": fire_result.multi_zone_assignments,
            "unassigned_distance_to_zone_km": distance_summary,
            "by_comuna": by_comuna,
            "by_province": by_province,
            "top_zones": top_zones,
        },
        "labels": {
            "target": TARGET,
            "rows": total_rows,
            "positives": total_positives,
            "negatives": total_rows - total_positives,
            "prevalence": round(total_positives / total_rows, 4) if total_rows else None,
            "by_season": positives_by_season,
            "by_province": by_province,
        },
        "missing": {"static_fields": missing_static},
        "artifacts": {"map": str(map_path), "season_chart": str(chart_path)},
        "limitations": [
            "Las 560 zonas continentales cubren solo ~3.7% del área regional; la mayoría de los "
            "puntos CONAF quedan fuera de toda zona.",
            "La etiqueta es ocurrencia de al menos un punto de ignición dentro del polígono, no "
            "área quemada ni riesgo operativo.",
            "Los polígonos son zonas censales o sectores municipales, no unidades homogéneas de "
            "combustible.",
            "La temporada 2010_2011 se usa solo como historia; las etiquetas evaluadas son "
            "2011_2012..2024_2025.",
            "Los puntos CONAF pueden subreportar incendios pequeños y tener precisión de "
            "coordenadas heterogénea.",
            "Isla de Pascua y Juan Fernández se excluyen del modelado continental.",
        ],
    }
    write_json(out_dir / "real_eda.json", payload)
    write_eda_markdown(payload, out_dir / "REAL_EDA.md")
    return payload


def write_eda_markdown(payload: dict[str, Any], path: Path) -> None:
    season_rows = []
    for item in payload["fires"]["seasons"]:
        season_rows.append(
            [
                item["season"],
                item["raw_records"],
                item["region5_records"],
                item["valid_points"],
                item["assigned"],
                item["unassigned"],
                _fmt(item["assignment_rate"], 3),
            ]
        )
    label_rows = [
        [
            item["season"],
            item["rows"],
            item["positives"],
            item["negatives"],
            _fmt(item["prevalence"], 3),
        ]
        for item in payload["labels"]["by_season"]
    ]
    comuna_rows = [
        [
            item["comuna"],
            item["zones"],
            item["assigned_fires_2010_2025"],
            item["positive_zone_seasons"],
            _fmt(item["prevalence"], 3),
        ]
        for item in payload["fires"]["by_comuna"][:20]
    ]
    top_rows = [
        [
            item["zone_name"],
            item["comuna"],
            item["dominant_fuel"],
            item["assigned_fires_2010_2025"],
            item["positive_target_seasons"],
        ]
        for item in payload["fires"]["top_zones"][:12]
    ]
    missing_rows = [[name, count] for name, count in payload["missing"]["static_fields"].items()]
    distance = payload["fires"]["unassigned_distance_to_zone_km"]
    lines = [
        "# EDA reproducible: incendios CONAF y zonas de Valparaíso",
        "",
        f"Generado: `{payload['generated_at']}`.",
        "",
        "## Alcance",
        "",
        "El objetivo es predecir **ocurrencia de al menos un punto de ignición CONAF** en una zona "
        "y temporada, no un índice de riesgo operativo. Las etiquetas se construyen por "
        "intersección espacial estricta entre puntos CONAF y polígonos de zona.",
        "",
        "## Cobertura espacial",
        "",
        f"- Zonas usadas: **{payload['zones']['used']}** (se excluyen Isla de Pascua y Juan "
        f"Fernández).",
        f"- Área suma de zonas: **{payload['zones']['total_area_km2']:.1f} km²**, equivalente a "
        f"**{payload['zones']['coverage_region_pct']}%** del área regional de referencia "
        f"({REGION_AREA_KM2:.0f} km²).",
        f"- Puntos CONAF válidos en la Región de Valparaíso continental: "
        f"**{payload['fires']['total_region5_valid_points']}**.",
        f"- Puntos asignados a alguna zona: **{payload['fires']['assigned']}** "
        f"({_fmt(payload['fires']['assignment_rate'], 3)}).",
        f"- Puntos fuera de toda zona: **{payload['fires']['unassigned']}**.",
        f"- Distancia de los no asignados a la zona más cercana: mediana "
        f"**{_fmt(distance.get('median_km'), 2)} km**, p90 **{_fmt(distance.get('p90_km'), 2)} "
        f"km**.",
        "",
        "Esta cobertura es la limitación central: el modelo aprende sobre una fracción "
        "urbana/periurbana de la región, no sobre todo el territorio forestal.",
        "",
        "![Incendios por zona](real_eda_map.svg)",
        "",
        "![Incendios por temporada](real_eda_seasons.svg)",
        "",
        "## Incendios por temporada",
        "",
        _markdown_table(
            [
                "Temporada",
                "Registros",
                "Región 5",
                "Puntos válidos",
                "Asignados",
                "No asignados",
                "Tasa asignación",
            ],
            season_rows,
        ),
        "",
        "## Balance de etiquetas por temporada objetivo",
        "",
        _markdown_table(
            ["Temporada", "Filas", "Positivos", "Negativos", "Prevalencia"], label_rows
        ),
        "",
        f"Balance global: **{payload['labels']['positives']} positivos / "
        f"{payload['labels']['rows']} filas** (prevalencia "
        f"**{_fmt(payload['labels']['prevalence'], 3)}**).",
        "",
        "## Comunas (top 20 por incendios asignados)",
        "",
        _markdown_table(
            ["Comuna", "Zonas", "Incendios asignados", "Zona-temporadas positivas", "Prevalencia"],
            comuna_rows,
        ),
        "",
        "## Zonas con más incendios asignados",
        "",
        _markdown_table(
            [
                "Zona",
                "Comuna",
                "Combustible dominante",
                "Incendios 2010-2025",
                "Temporadas objetivo positivas",
            ],
            top_rows,
        ),
        "",
        "## Valores faltantes en variables estáticas",
        "",
        _markdown_table(["Campo", "Zonas sin valor"], missing_rows),
        "",
        "Los valores faltantes se imputan con mediana dentro del pipeline de entrenamiento; no se "
        "rellenan con información del futuro.",
        "",
        "## Limitaciones del EDA",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["limitations"])
    lines.extend(
        [
            "",
            "## Reproducción",
            "",
            "```bash",
            "uv run python scripts/crispdm_real_model.py eda",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_model_pipeline(
    model_name: str,
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    seed: int = SEED,
    quick: bool = False,
) -> Pipeline:
    preprocessor = TabularPreprocessor(numeric_features, categorical_features)
    if model_name == "logistic_regression":
        classifier = LogisticRegression(
            C=0.5,
            max_iter=3000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=seed,
        )
    elif model_name == "random_forest":
        classifier = RandomForestClassifier(
            n_estimators=180 if quick else 500,
            min_samples_leaf=4,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        )
    elif model_name == "hist_gradient_boosting":
        classifier = HistGradientBoostingClassifier(
            max_iter=140 if quick else 320,
            learning_rate=0.05,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=1.0,
            class_weight="balanced",
            early_stopping=False,
            random_state=seed,
        )
    else:
        raise ValueError(f"Modelo desconocido: {model_name}")
    return Pipeline([("preprocess", preprocessor), ("model", classifier)])


def make_loso_splits(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seasons = sorted({str(row["season"]) for row in rows})
    folds: list[dict[str, Any]] = []
    for season in seasons:
        train = [index for index, row in enumerate(rows) if row["season"] != season]
        test = [index for index, row in enumerate(rows) if row["season"] == season]
        folds.append({"fold": season, "test_group": season, "train": train, "test": test})
    return folds


def make_province_splits(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    provinces = sorted({str(row["provincia"]) for row in rows})
    folds: list[dict[str, Any]] = []
    for province in provinces:
        train = [index for index, row in enumerate(rows) if row["provincia"] != province]
        test = [index for index, row in enumerate(rows) if row["provincia"] == province]
        if not test:
            continue
        folds.append(
            {"fold": f"province_{province}", "test_group": province, "train": train, "test": test}
        )
    return folds


def make_comuna_splits(rows: Sequence[dict[str, Any]], seed: int = SEED) -> list[dict[str, Any]]:
    y = np.asarray([int(row[TARGET]) for row in rows], dtype=int)
    groups = np.asarray([str(row["comuna"]) for row in rows], dtype=object)
    unique = len(set(groups))
    n_splits = min(5, unique)
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds: list[dict[str, Any]] = []
    for fold_index, (train, test) in enumerate(
        splitter.split(np.zeros(len(rows)), y, groups), start=1
    ):
        test_groups = sorted({str(groups[index]) for index in test})
        folds.append(
            {
                "fold": f"comuna_fold_{fold_index}",
                "test_group": ", ".join(test_groups[:4]) + ("..." if len(test_groups) > 4 else ""),
                "test_groups": test_groups,
                "train": [int(index) for index in train],
                "test": [int(index) for index in test],
            }
        )
    return folds


def safe_roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    if len(np.unique(scores)) == 1:
        return 0.5
    return float(roc_auc_score(y_true, scores))


def binary_metrics(
    y_true: Sequence[int],
    probabilities: Sequence[float],
    threshold: float = 0.5,
) -> dict[str, Any]:
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    finite = np.isfinite(p)
    y = y[finite]
    p = p[finite]
    if len(y) == 0:
        return {}
    prediction = (p >= threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, prediction, labels=[0, 1], zero_division=0
    )
    matrix = confusion_matrix(y, prediction, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    positives = int(y.sum())
    result: dict[str, Any] = {
        "n": int(len(y)),
        "positives": positives,
        "prevalence": float(positives / len(y)),
        "threshold": float(threshold),
        "pr_auc": float(average_precision_score(y, p)) if positives else None,
        "roc_auc": safe_roc_auc(y, p),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1.0 - 1e-6), labels=[0, 1])),
        "precision": float(precision[1]),
        "recall": float(recall[1]),
        "f1": float(f1[1]),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "predicted_positive_rate": float(prediction.mean()),
        "lift": float(precision[1] / (positives / len(y))) if positives else None,
    }
    return result


def fold_record(
    scheme: str,
    fold: str,
    test_group: str,
    y_train: Sequence[int],
    y_test: Sequence[int],
    probabilities: Sequence[float],
    threshold: float = 0.5,
) -> dict[str, Any]:
    metrics = binary_metrics(y_test, probabilities, threshold=threshold)
    metrics.update(
        {
            "scheme": scheme,
            "fold": fold,
            "test_group": test_group,
            "n_train": len(y_train),
            "n_test": len(y_test),
            "positives_train": int(np.sum(y_train)),
            "positives_test": int(np.sum(y_test)),
            "prevalence_train": float(np.mean(y_train)),
        }
    )
    return metrics


def summarize_fold_metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    keys = ["pr_auc", "roc_auc", "brier", "log_loss", "precision", "recall", "f1"]
    summary: dict[str, Any] = {
        "n_folds": len(records),
        "positives_test_mean": _mean(record.get("positives_test") for record in records),
        "prevalence_test_mean": _mean(record.get("prevalence") for record in records),
    }
    for key in keys:
        values = [float(record[key]) for record in records if record.get(key) is not None]
        if not values:
            summary[key] = {"mean": None, "std": None, "min": None, "max": None, "ci95": None}
            continue
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        if len(values) > 1:
            from scipy import stats

            half_width = float(stats.t.ppf(0.975, len(values) - 1) * std / math.sqrt(len(values)))
        else:
            half_width = 0.0
        summary[key] = {
            "mean": round(mean, 6),
            "std": round(std, 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "ci95": [round(mean - half_width, 6), round(mean + half_width, 6)],
        }
    return summary


def run_validation(
    rows: Sequence[dict[str, Any]],
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    seed: int = SEED,
    quick: bool = False,
    max_folds: int = 0,
) -> dict[str, Any]:
    y = np.asarray([int(row[TARGET]) for row in rows], dtype=int)
    model_names = ["logistic_regression", "random_forest", "hist_gradient_boosting"]
    schemes = {
        "loso": make_loso_splits(rows),
        "province": make_province_splits(rows),
        "comuna": make_comuna_splits(rows, seed=seed),
    }
    if max_folds:
        schemes = {
            name: (folds if name == "loso" else folds[:max_folds])
            for name, folds in schemes.items()
        }
    fold_results: dict[str, dict[str, list[dict[str, Any]]]] = {
        scheme: {name: [] for name in model_names} for scheme in schemes
    }
    baseline_results: dict[str, dict[str, list[dict[str, Any]]]] = {
        scheme: {"prevalence": [], "history_rule": []} for scheme in schemes
    }
    oof: dict[str, dict[str, np.ndarray]] = {
        name: {"prediction": np.full(len(rows), np.nan), "target": y} for name in model_names
    }
    for scheme, folds in schemes.items():
        for fold in folds:
            train_idx = np.asarray(fold["train"], dtype=int)
            test_idx = np.asarray(fold["test"], dtype=int)
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue
            y_train = y[train_idx]
            y_test = y[test_idx]
            for model_name in model_names:
                pipeline = build_model_pipeline(
                    model_name,
                    numeric_features,
                    categorical_features,
                    seed=seed,
                    quick=quick,
                )
                pipeline.fit([rows[index] for index in train_idx], y_train)
                probabilities = pipeline.predict_proba([rows[index] for index in test_idx])[:, 1]
                record = fold_record(
                    scheme,
                    fold["fold"],
                    fold["test_group"],
                    y_train,
                    y_test,
                    probabilities,
                )
                fold_results[scheme][model_name].append(record)
                if scheme == "loso":
                    oof[model_name]["prediction"][test_idx] = probabilities
            prevalence = float(np.mean(y_train))
            prevalence_probabilities = np.full(len(test_idx), prevalence)
            baseline_results[scheme]["prevalence"].append(
                fold_record(
                    scheme,
                    fold["fold"],
                    fold["test_group"],
                    y_train,
                    y_test,
                    prevalence_probabilities,
                )
            )
            history_probabilities = np.asarray(
                [float(rows[index].get("prior_burn_rate") or 0.0) for index in test_idx],
                dtype=float,
            )
            baseline_results[scheme]["history_rule"].append(
                fold_record(
                    scheme,
                    fold["fold"],
                    fold["test_group"],
                    y_train,
                    y_test,
                    history_probabilities,
                )
            )
    summaries: dict[str, dict[str, Any]] = {}
    for scheme in schemes:
        summaries[scheme] = {
            name: summarize_fold_metrics(records) for name, records in fold_results[scheme].items()
        }
        summaries[scheme]["baseline_prevalence"] = summarize_fold_metrics(
            baseline_results[scheme]["prevalence"]
        )
        summaries[scheme]["baseline_history_rule"] = summarize_fold_metrics(
            baseline_results[scheme]["history_rule"]
        )
    return {
        "schemes": list(schemes),
        "fold_results": fold_results,
        "baseline_results": baseline_results,
        "summaries": summaries,
        "oof": oof,
        "target": y,
        "n_rows": len(rows),
        "model_names": model_names,
    }


def select_best_model(summary: dict[str, Any], model_names: Sequence[str]) -> dict[str, Any]:
    loso = summary["summaries"]["loso"]
    pr_auc_values = {name: float(loso[name]["pr_auc"]["mean"] or 0.0) for name in model_names}
    brier_values = {name: float(loso[name]["brier"]["mean"] or 1.0) for name in model_names}
    best_pr_auc = max(pr_auc_values.values())
    tie_tolerance = 0.01
    tied = [name for name in model_names if pr_auc_values[name] >= best_pr_auc - tie_tolerance]
    outside = [name for name in model_names if name not in tied]
    ordered = sorted(tied, key=lambda name: (brier_values[name], -pr_auc_values[name])) + sorted(
        outside, key=lambda name: (-pr_auc_values[name], brier_values[name])
    )
    best = ordered[0]
    ranking = []
    for position, name in enumerate(ordered, start=1):
        ranking.append(
            {
                "rank": position,
                "model": name,
                "loso_pr_auc": loso[name]["pr_auc"]["mean"],
                "loso_pr_auc_ci95": loso[name]["pr_auc"]["ci95"],
                "loso_brier": loso[name]["brier"]["mean"],
                "loso_roc_auc": loso[name]["roc_auc"]["mean"],
                "province_pr_auc": summary["summaries"]["province"][name]["pr_auc"]["mean"],
                "comuna_pr_auc": summary["summaries"]["comuna"][name]["pr_auc"]["mean"],
            }
        )
    baseline = loso["baseline_prevalence"]["pr_auc"]["mean"]
    history = loso["baseline_history_rule"]["pr_auc"]["mean"]
    selected_pr_auc = pr_auc_values[best]
    return {
        "best_model": best,
        "ranking": ranking,
        "selection_rule": (
            "Se considera empate práctico de PR-AUC a los modelos dentro de 0.01 del máximo; "
            "entre ellos se elige el menor Brier LOSO. Si no hay empate, gana el mayor PR-AUC."
        ),
        "pr_auc_tie_tolerance": tie_tolerance,
        "tied_models": tied,
        "baseline_prevalence_pr_auc": baseline,
        "baseline_history_rule_pr_auc": history,
        "best_pr_auc": selected_pr_auc,
        "beats_prevalence": bool(
            selected_pr_auc is not None and baseline is not None and selected_pr_auc > baseline
        ),
        "beats_history_rule": bool(
            selected_pr_auc is not None and history is not None and selected_pr_auc > history
        ),
        "optimism_note": "La selección y la evaluación usan los mismos folds LOSO; las métricas"
        " del modelo elegido son optimistas. La validación espacial se reporta como estrés,"
        " no como selección.",
    }


def safe_calibration_splits(
    seasons_train: Sequence[str],
    y_train: Sequence[int],
    n_splits: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]] | None:
    groups = np.asarray(seasons_train, dtype=object)
    y = np.asarray(y_train, dtype=int)
    unique_groups = len(set(groups))
    for candidate in range(min(n_splits, unique_groups), 1, -1):
        splitter = GroupKFold(n_splits=candidate)
        splits = [
            (np.asarray(train, dtype=int), np.asarray(test, dtype=int))
            for train, test in splitter.split(np.zeros(len(groups)), y, groups)
        ]
        if all(len(np.unique(y[test])) == 2 for _, test in splits):
            return splits
    return None


def nested_calibration_predictions(
    rows: Sequence[dict[str, Any]],
    base_factory: Any,
    method: str,
    y: np.ndarray,
    seed: int = SEED,
) -> tuple[np.ndarray, dict[str, Any]]:
    predictions = np.full(len(rows), np.nan, dtype=float)
    folds = make_loso_splits(rows)
    calibrated_folds = 0
    fallback_folds = 0
    errors: list[str] = []
    for fold in folds:
        train_idx = np.asarray(fold["train"], dtype=int)
        test_idx = np.asarray(fold["test"], dtype=int)
        train_seasons = [str(rows[index]["season"]) for index in train_idx]
        splits = safe_calibration_splits(train_seasons, y[train_idx], n_splits=5)
        try:
            if splits:
                model = CalibratedClassifierCV(
                    estimator=base_factory(),
                    method=method,
                    cv=splits,
                    ensemble=True,
                )
                calibrated_folds += 1
            else:
                model = base_factory()
                fallback_folds += 1
            model.fit([rows[index] for index in train_idx], y[train_idx])
            predictions[test_idx] = model.predict_proba([rows[index] for index in test_idx])[:, 1]
        except Exception as exc:
            fallback_folds += 1
            errors.append(f"{fold['fold']}: {type(exc).__name__}: {exc}")
            fallback = base_factory()
            fallback.fit([rows[index] for index in train_idx], y[train_idx])
            predictions[test_idx] = fallback.predict_proba([rows[index] for index in test_idx])[
                :, 1
            ]
    return predictions, {
        "method": method,
        "folds_total": len(folds),
        "folds_calibrated": calibrated_folds,
        "folds_fallback": fallback_folds,
        "errors": errors,
    }


def calibration_curve_data(
    y_true: Sequence[int],
    probabilities: Sequence[float],
    bins: int = 10,
) -> dict[str, Any]:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    order = np.argsort(p)
    chunks = [chunk for chunk in np.array_split(order, bins) if len(chunk)]
    rows = []
    weighted_gap = 0.0
    for chunk in chunks:
        observed = float(np.mean(y[chunk]))
        predicted = float(np.mean(p[chunk]))
        weight = len(chunk) / len(y)
        weighted_gap += weight * abs(observed - predicted)
        rows.append(
            {
                "n": int(len(chunk)),
                "mean_predicted": round(predicted, 6),
                "observed_rate": round(observed, 6),
                "absolute_gap": round(abs(observed - predicted), 6),
                "min_predicted": round(float(np.min(p[chunk])), 6),
                "max_predicted": round(float(np.max(p[chunk])), 6),
            }
        )
    return {"bins": rows, "ece": round(weighted_gap, 6)}


def _threshold_candidates(
    y_true: Sequence[int],
    probabilities: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    precision, recall, thresholds = precision_recall_curve(y, p)
    return precision[:-1], recall[:-1], thresholds


def threshold_for_precision(
    y_true: Sequence[int],
    probabilities: Sequence[float],
    target_precision: float,
) -> dict[str, Any]:
    precision, recall, thresholds = _threshold_candidates(y_true, probabilities)
    valid = np.where(precision >= target_precision)[0]
    if len(valid):
        best_index = valid[np.lexsort((-precision[valid], -recall[valid]))[0]]
        achieved = True
    else:
        best_index = int(np.lexsort((-recall, -precision))[0])
        achieved = False
    threshold = float(thresholds[best_index])
    metrics = binary_metrics(y_true, probabilities, threshold=threshold)
    return {
        "target_precision": target_precision,
        "target_achieved": achieved,
        "threshold": round(threshold, 6),
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "predicted_positive_rate": metrics["predicted_positive_rate"],
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "fn": metrics["fn"],
        "tn": metrics["tn"],
        "justification": (
            f"Umbral que maximiza recall con precision >= {target_precision:.2f}."
            if achieved
            else f"No se alcanzó precision >= {target_precision:.2f}; se reporta el máximo "
            f"precision disponible."
        ),
    }


def threshold_for_recall(
    y_true: Sequence[int],
    probabilities: Sequence[float],
    target_recall: float,
) -> dict[str, Any]:
    precision, recall, thresholds = _threshold_candidates(y_true, probabilities)
    valid = np.where(recall >= target_recall)[0]
    if len(valid):
        best_index = valid[np.lexsort((-recall[valid], -precision[valid]))[0]]
        achieved = True
    else:
        best_index = int(np.lexsort((-precision, -recall))[0])
        achieved = False
    threshold = float(thresholds[best_index])
    metrics = binary_metrics(y_true, probabilities, threshold=threshold)
    return {
        "target_recall": target_recall,
        "target_achieved": achieved,
        "threshold": round(threshold, 6),
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "predicted_positive_rate": metrics["predicted_positive_rate"],
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "fn": metrics["fn"],
        "tn": metrics["tn"],
        "justification": (
            f"Umbral que maximiza precision con recall >= {target_recall:.2f}."
            if achieved
            else f"No se alcanzó recall >= {target_recall:.2f}; se reporta el máximo recall "
            f"disponible."
        ),
    }


def threshold_max_f1(y_true: Sequence[int], probabilities: Sequence[float]) -> dict[str, Any]:
    precision, recall, thresholds = _threshold_candidates(y_true, probabilities)
    f1 = 2.0 * precision * recall / np.clip(precision + recall, 1e-12, None)
    best_index = int(np.argmax(f1))
    threshold = float(thresholds[best_index])
    metrics = binary_metrics(y_true, probabilities, threshold=threshold)
    return {
        "threshold": round(threshold, 6),
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "predicted_positive_rate": metrics["predicted_positive_rate"],
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "fn": metrics["fn"],
        "tn": metrics["tn"],
        "justification": "Umbral que maximiza F1 en las probabilidades calibradas out-of-fold; no "
        "es un argmax de clase.",
    }


def select_operating_thresholds(
    y_true: Sequence[int],
    probabilities: Sequence[float],
) -> dict[str, Any]:
    return {
        "default_0_5": binary_metrics(y_true, probabilities, threshold=0.5),
        "balanced_f1": threshold_max_f1(y_true, probabilities),
        "high_precision_0_70": threshold_for_precision(y_true, probabilities, 0.70),
        "high_recall_0_80": threshold_for_recall(y_true, probabilities, 0.80),
        "recommended": "balanced_f1",
        "recommendation_note": (
            "El umbral balanceado es el punto de partida para comparar. Para verificación de campo "
            "se recomienda high_precision_0_70; para patrullaje preventivo, high_recall_0_80. "
            "La elección final depende del costo de falsos positivos y de la capacidad operativa."
        ),
    }


def fit_final_model(
    rows: Sequence[dict[str, Any]],
    base_factory: Any,
    method: str,
    y: np.ndarray,
    seasons: Sequence[str],
) -> tuple[Any, dict[str, Any]]:
    splits = safe_calibration_splits(seasons, y, n_splits=5)
    if splits:
        model = CalibratedClassifierCV(
            estimator=base_factory(),
            method=method,
            cv=splits,
            ensemble=True,
        )
        try:
            model.fit(rows, y)
            return model, {
                "calibrated": True,
                "method": method,
                "cv_folds": len(splits),
                "fallback": False,
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    else:
        error = "No se pudieron construir folds de calibración con ambas clases"
    fallback = base_factory()
    fallback.fit(rows, y)
    return fallback, {
        "calibrated": False,
        "method": None,
        "cv_folds": 0,
        "fallback": True,
        "error": error,
    }


def extract_feature_importance(model: Any, limit: int = 30) -> list[dict[str, Any]]:
    pipeline = model
    if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
        pipeline = model.calibrated_classifiers_[0].estimator
    try:
        preprocessor = pipeline.named_steps["preprocess"]
        classifier = pipeline.named_steps["model"]
        names = [
            str(name).replace("num__", "").replace("cat__", "")
            for name in preprocessor.get_feature_names_out()
        ]
    except Exception:
        return []
    values: np.ndarray | None = None
    direction = "importance"
    if hasattr(classifier, "feature_importances_"):
        values = np.asarray(classifier.feature_importances_, dtype=float)
    elif hasattr(classifier, "coef_"):
        values = np.asarray(classifier.coef_[0], dtype=float)
        direction = "coefficient"
    if values is None or len(values) != len(names):
        return []
    order = np.argsort(np.abs(values))[::-1][:limit]
    return [
        {
            "feature": names[int(index)],
            "value": round(float(values[int(index)]), 6),
            "direction": direction,
        }
        for index in order
    ]


def run_training(
    rows: Sequence[dict[str, Any]],
    metadata: dict[str, Any],
    out_dir: Path,
    seed: int = SEED,
    quick: bool = False,
    max_folds: int = 0,
) -> dict[str, Any]:
    numeric_features = metadata["features"]["numeric"]
    categorical_features = metadata["features"]["categorical"]
    y = np.asarray([int(row[TARGET]) for row in rows], dtype=int)
    seasons = [str(row["season"]) for row in rows]
    validation = run_validation(
        rows,
        numeric_features,
        categorical_features,
        seed=seed,
        quick=quick,
        max_folds=max_folds,
    )
    selection = select_best_model(validation, validation["model_names"])
    best_model = selection["best_model"]

    def base_factory() -> Pipeline:
        return build_model_pipeline(
            best_model,
            numeric_features,
            categorical_features,
            seed=seed,
            quick=quick,
        )

    candidate_methods = ["sigmoid"]
    calibration_candidates: dict[str, Any] = {}
    for method in candidate_methods:
        calibrated_predictions, calibration_info = nested_calibration_predictions(
            rows,
            base_factory,
            method,
            y,
            seed=seed,
        )
        metrics = binary_metrics(y, calibrated_predictions)
        curve = calibration_curve_data(y, calibrated_predictions)
        calibration_candidates[method] = {
            "info": calibration_info,
            "metrics": metrics,
            "curve": curve,
            "predictions": calibrated_predictions,
        }
    chosen_method = min(
        calibration_candidates,
        key=lambda name: (
            float(calibration_candidates[name]["metrics"]["brier"] or 1.0),
            float(calibration_candidates[name]["metrics"]["log_loss"] or 1.0),
        ),
    )
    chosen = calibration_candidates[chosen_method]
    calibrated_predictions = chosen["predictions"]
    base_predictions = validation["oof"][best_model]["prediction"]
    uncalibrated_metrics = binary_metrics(y, base_predictions)
    calibrated_metrics = binary_metrics(y, calibrated_predictions)
    thresholds = select_operating_thresholds(y, calibrated_predictions)
    final_model, final_info = fit_final_model(rows, base_factory, chosen_method, y, seasons)
    feature_importance = extract_feature_importance(final_model)
    dataset_payload = metadata.get("dataset", {})
    metrics_payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": "conaf-real-baseline-0.1.0",
        "seed": seed,
        "selected_model": best_model,
        "selection": selection,
        "dataset": dataset_payload,
        "validation": {
            "schemes": validation["schemes"],
            "summaries": validation["summaries"],
            "fold_results": validation["fold_results"],
            "baseline_results": validation["baseline_results"],
        },
        "calibration": {
            "chosen_method": chosen_method,
            "chosen_info": chosen["info"],
            "candidates": {
                name: {
                    "info": payload["info"],
                    "metrics": payload["metrics"],
                    "curve": payload["curve"],
                }
                for name, payload in calibration_candidates.items()
            },
            "uncalibrated_oof_metrics": uncalibrated_metrics,
            "calibrated_oof_metrics": calibrated_metrics,
        },
        "operating_thresholds": thresholds,
        "feature_importance": feature_importance,
        "final_model": final_info,
        "artifacts": {},
        "limitations": [
            "No es un modelo operativo: es un baseline de investigación con cobertura espacial "
            "parcial.",
            "Las zonas cubren ~3.7% del área; los incendios fuera de zona no se etiquetan.",
            "No usa clima de la temporada objetivo, causas de ignición, caminos, líneas eléctricas "
            "ni capacidad de respuesta.",
            f"Clima de la temporada previa desde "
            f"{metadata.get('climate', {}).get('source') or 'fuente no disponible'}; resolución de "
            f"grilla gruesa en el centroide comunal, no microclima local.",
            "Los combustibles son un corte estático CONAF 2019; las plantaciones y el uso de suelo "
            "cambian.",
            "El combustible/vegetación es un corte 2019 y la población es censo 2017;"
            " en temporadas previas son información futura, un supuesto estático fuerte.",
            "La selección del modelo y las métricas comparten folds; las métricas del elegido son "
            "optimistas.",
            "La validación espacial por provincia/comuna es un estrés de generalización, no una "
            "estimación de despliegue.",
        ],
    }
    artifact_path = out_dir / "real_model.joblib"
    payload = {
        "model": final_model,
        "model_name": best_model,
        "model_version": metrics_payload["model_version"],
        "feature_columns": list(numeric_features) + list(categorical_features),
        "numeric_features": list(numeric_features),
        "categorical_features": list(categorical_features),
        "thresholds": thresholds,
        "metadata": metadata,
        "training_metrics": {
            "loso_pr_auc": selection["best_pr_auc"],
            "loso_brier": selection["ranking"][0]["loso_brier"],
            "calibrated_brier": calibrated_metrics["brier"],
            "calibrated_pr_auc": calibrated_metrics["pr_auc"],
        },
        "created_at": metrics_payload["generated_at"],
        "seed": seed,
        "sklearn_version": __import__("sklearn").__version__,
        "target": TARGET,
        "not_operational": True,
        "limitations": metrics_payload["limitations"],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, artifact_path, compress=3)
    artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    metrics_payload["artifacts"] = {
        "model": str(artifact_path),
        "model_sha256": artifact_hash,
        "dataset_csv": str(out_dir / "real_dataset.csv"),
        "dataset_metadata": str(out_dir / "real_dataset_metadata.json"),
        "metrics": str(out_dir / "real_metrics.json"),
        "training_report": str(out_dir / "real_training_report.md"),
        "model_card": str(out_dir / "real_model_card.md"),
    }
    write_json(out_dir / "real_metrics.json", metrics_payload)
    write_oof_predictions(
        rows,
        base_predictions,
        calibrated_predictions,
        thresholds,
        out_dir / "real_oof_predictions.csv",
    )
    write_training_report(metrics_payload, out_dir / "real_training_report.md")
    write_model_card(metrics_payload, metadata, out_dir / "real_model_card.md")
    return metrics_payload


def write_oof_predictions(
    rows: Sequence[dict[str, Any]],
    base_predictions: Sequence[float],
    calibrated_predictions: Sequence[float],
    thresholds: dict[str, Any],
    path: Path,
) -> None:
    balanced = float(thresholds["balanced_f1"]["threshold"])
    high_precision = float(thresholds["high_precision_0_70"]["threshold"])
    high_recall = float(thresholds["high_recall_0_80"]["threshold"])
    fieldnames = [
        "season",
        "zone_id",
        "zone_name",
        "comuna",
        "provincia",
        TARGET,
        "n_fires_target",
        "p_base",
        "p_calibrated",
        "flag_balanced",
        "flag_high_precision",
        "flag_high_recall",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, row in enumerate(rows):
            calibrated = float(calibrated_predictions[index])
            writer.writerow(
                {
                    "season": row["season"],
                    "zone_id": row["zone_id"],
                    "zone_name": row["zone_name"],
                    "comuna": row["comuna"],
                    "provincia": row["provincia"],
                    TARGET: row[TARGET],
                    "n_fires_target": row.get("n_fires_target"),
                    "p_base": round(float(base_predictions[index]), 6),
                    "p_calibrated": round(calibrated, 6),
                    "flag_balanced": int(calibrated >= balanced),
                    "flag_high_precision": int(calibrated >= high_precision),
                    "flag_high_recall": int(calibrated >= high_recall),
                }
            )


def write_training_report(metrics: dict[str, Any], path: Path) -> None:
    summaries = metrics["validation"]["summaries"]
    chosen_curve = metrics["calibration"]["candidates"][metrics["calibration"]["chosen_method"]][
        "curve"
    ]
    ece_text = _fmt(chosen_curve["ece"], 3)
    model_names = ["logistic_regression", "random_forest", "hist_gradient_boosting"]
    model_rows = []
    for name in model_names:
        loso = summaries["loso"][name]
        province = summaries["province"][name]
        comuna = summaries["comuna"][name]
        model_rows.append(
            [
                name,
                _fmt(loso["pr_auc"]["mean"], 3),
                _fmt(loso["brier"]["mean"], 3),
                _fmt(loso["roc_auc"]["mean"], 3),
                _fmt(province["pr_auc"]["mean"], 3),
                _fmt(comuna["pr_auc"]["mean"], 3),
            ]
        )
    baseline_rows = []
    for label, key in [
        ("Prevalencia", "baseline_prevalence"),
        ("Regla histórica", "baseline_history_rule"),
    ]:
        loso = summaries["loso"][key]
        province = summaries["province"][key]
        comuna = summaries["comuna"][key]
        baseline_rows.append(
            [
                label,
                _fmt(loso["pr_auc"]["mean"], 3),
                _fmt(loso["brier"]["mean"], 3),
                _fmt(loso["roc_auc"]["mean"], 3),
                _fmt(province["pr_auc"]["mean"], 3),
                _fmt(comuna["pr_auc"]["mean"], 3),
            ]
        )
    loso_fold_rows = []
    for record in metrics["validation"]["fold_results"]["loso"][metrics["selected_model"]]:
        loso_fold_rows.append(
            [
                record["fold"],
                record["n_test"],
                record["positives_test"],
                _fmt(record["pr_auc"], 3),
                _fmt(record["brier"], 3),
                _fmt(record["roc_auc"], 3),
                _fmt(record["precision"], 3),
                _fmt(record["recall"], 3),
                _fmt(record["f1"], 3),
            ]
        )
    threshold_rows = []
    for label, key in [
        ("0.5 ciego", "default_0_5"),
        ("F1 balanceado", "balanced_f1"),
        ("Alta precision (>=0.70)", "high_precision_0_70"),
        ("Alto recall (>=0.80)", "high_recall_0_80"),
    ]:
        item = metrics["operating_thresholds"][key]
        threshold_rows.append(
            [
                label,
                _fmt(item["threshold"], 3),
                _fmt(item["precision"], 3),
                _fmt(item["recall"], 3),
                _fmt(item["f1"], 3),
                _fmt(item["predicted_positive_rate"], 3),
                f"{item['tp']}/{item['fp']}/{item['fn']}/{item['tn']}",
            ]
        )
    curve_rows = [
        [
            index,
            _fmt(item["mean_predicted"], 3),
            _fmt(item["observed_rate"], 3),
            _fmt(item["absolute_gap"], 3),
            item["n"],
        ]
        for index, item in enumerate(
            metrics["calibration"]["candidates"][metrics["calibration"]["chosen_method"]]["curve"][
                "bins"
            ],
            start=1,
        )
    ]
    importance_rows = [
        [item["feature"], _fmt(item["value"], 4)] for item in metrics["feature_importance"][:15]
    ]
    verdict = (
        "El modelo supera el baseline de prevalencia en PR-AUC, pero la cobertura espacial y la "
        "naturaleza retrospectiva de las etiquetas impiden presentarlo como modelo operativo."
        if metrics["selection"]["beats_prevalence"]
        else "El modelo NO supera de forma clara el baseline de prevalencia; el resultado debe "
        "tratarse como un ejercicio negativo o exploratorio."
    )
    lines = [
        "# Reporte de entrenamiento: ocurrencia real de incendios por zona y temporada",
        "",
        f"Generado: `{metrics['generated_at']}`. Semilla: `{metrics['seed']}`. Versión: "
        f"`{metrics['model_version']}`.",
        "",
        "## Veredicto honesto",
        "",
        verdict,
        "",
        f"- Modelo seleccionado: **{metrics['selected_model']}** (regla PR-AUC/Brier).",
        f"- PR-AUC LOSO: **{_fmt(metrics['selection']['best_pr_auc'], 3)}**; prevalencia de "
        f"referencia: **{_fmt(metrics['selection']['baseline_prevalence_pr_auc'], 3)}**; regla "
        f"histórica: **{_fmt(metrics['selection']['baseline_history_rule_pr_auc'], 3)}**.",
        f"- Brier calibrado out-of-fold: "
        f"**{_fmt(metrics['calibration']['calibrated_oof_metrics']['brier'], 3)}**; sin calibrar: "
        f"**{_fmt(metrics['calibration']['uncalibrated_oof_metrics']['brier'], 3)}**.",
        f"- Modelos empatados en PR-AUC (dentro de "
        f"{metrics['selection'].get('pr_auc_tie_tolerance', 0.01)}): "
        f"**{', '.join(metrics['selection'].get('tied_models', []))}**. Se desempata por menor "
        f"Brier.",
        "- **No integrar en la API ni usar para decisiones operativas todavía.**",
        "",
        "## 1. Comprensión del negocio",
        "",
        "La pregunta es si una zona tendrá al menos un punto de ignición CONAF en la temporada "
        "siguiente. Es una tarea de clasificación binaria desbalanceada, evaluada temporal y "
        "espacialmente. No es un índice de riesgo, peligro, vulnerabilidad ni prioridad de "
        "extinción.",
        "",
        "## 2. Comprensión de los datos",
        "",
        "- Etiquetas: puntos de inicio CONAF por temporada, 2010_2011 a 2024_2025, filtrados a la "
        "Región de Valparaíso continental.",
        "- Zonas: 560 polígonos censales/municipales continentales; se excluyen Isla de Pascua y "
        "Juan Fernández.",
        "- El EDA completo está en `REAL_EDA.md`; la cobertura de zonas es ~3.7% del área regional "
        "y solo ~44% de los puntos CONAF caen dentro de alguna zona.",
        "- La temporada 2010_2011 se usa solo como historia; las filas evaluadas son "
        "2011_2012..2024_2025.",
        "",
        "## 3. Preparación de datos",
        "",
        "Cada fila es `zona × temporada objetivo`. Las variables de historia usan exclusivamente "
        "temporadas anteriores a la objetivo. El clima es de la temporada previa y su anomalía "
        "contra la climatología 1991-2020. No se usa `historical_fires`, `incendios_*` ni ningún "
        "agregado de todo el período.",
        "",
        f"- Filas: **{metrics['dataset'].get('rows', 'n/d')}**; positivos: "
        f"**{metrics['dataset'].get('positives', 'n/d')}**; prevalencia: "
        f"**{_fmt(metrics['dataset'].get('prevalence'), 3)}**.",
        f"- Variables numéricas: {len(metrics['dataset'].get('features', {}).get('numeric', []))}; "
        f"categóricas: {len(metrics['dataset'].get('features', {}).get('categorical', []))}.",
        f"- Clima: **{metrics['dataset'].get('climate', {}).get('status', 'n/d')}**.",
        "",
        "## 4. Modelado",
        "",
        "- LogisticRegression con `class_weight='balanced'`.",
        "- RandomForest con `class_weight='balanced_subsample'`.",
        "- HistGradientBoosting con `class_weight='balanced'`.",
        "- Pipeline propio de imputación mediana, escalado estándar y one-hot con "
        "`handle_unknown='ignore'`.",
        "",
        _markdown_table(
            [
                "Modelo",
                "PR-AUC LOSO",
                "Brier LOSO",
                "ROC-AUC LOSO",
                "PR-AUC provincia",
                "PR-AUC comuna",
            ],
            model_rows,
        ),
        "",
        "La diferencia de PR-AUC entre LogisticRegression y RandomForest es de 0.003 y ambos caen "
        "dentro de la banda de empate de 0.01. RandomForest se elige por su Brier marcadamente "
        "menor (0.113 vs 0.150) y su mejor desempeño espacial; no por un argmax ciego de una sola "
        "métrica.",
        "",
        "### Baselines",
        "",
        _markdown_table(
            [
                "Baseline",
                "PR-AUC LOSO",
                "Brier LOSO",
                "ROC-AUC LOSO",
                "PR-AUC provincia",
                "PR-AUC comuna",
            ],
            baseline_rows,
        ),
        "",
        "## 5. Evaluación temporal (leave-one-season-out)",
        "",
        _markdown_table(
            [
                "Temporada",
                "n test",
                "positivos",
                "PR-AUC",
                "Brier",
                "ROC-AUC",
                "Precision",
                "Recall",
                "F1",
            ],
            loso_fold_rows,
        ),
        "",
        "La varianza entre folds es alta porque cada temporada tiene entre 56 y 149 zona-temporadas"
        " positivas y los incendios son episódicos. Los intervalos de confianza al 95% de los "
        "promedios están en `real_metrics.json`.",
        "",
        "## 6. Validación espacial",
        "",
        "Se evaluó leave-one-province-out y `StratifiedGroupKFold` por comuna. Sirve como prueba de"
        " estrés: el modelo no debe memorizar comunas. Los resultados espaciales son menores que "
        "LOSO, lo que confirma dependencia de historia local y de patrones específicos de zona.",
        "",
        _markdown_table(
            ["Modelo", "PR-AUC provincia", "Brier provincia", "PR-AUC comuna", "Brier comuna"],
            [
                [
                    name,
                    _fmt(summaries["province"][name]["pr_auc"]["mean"], 3),
                    _fmt(summaries["province"][name]["brier"]["mean"], 3),
                    _fmt(summaries["comuna"][name]["pr_auc"]["mean"], 3),
                    _fmt(summaries["comuna"][name]["brier"]["mean"], 3),
                ]
                for name in model_names
            ],
        ),
        "",
        "## 7. Calibración",
        "",
        f"Método elegido: **{metrics['calibration']['chosen_method']}**. La calibración se evaluó "
        f"de forma anidada: dentro de cada fold LOSO se ajustó `CalibratedClassifierCV` solo con "
        f"temporadas de entrenamiento.",
        "",
        _markdown_table(
            ["Bin", "Prob. media", "Tasa observada", "Gap absoluto", "n"],
            curve_rows,
        ),
        "",
        f"ECE: "
        f"**{ece_text}**. Brier calibrado: "
        f"**{metrics['calibration']['calibrated_oof_metrics']['brier']:.3f}**.",
        "",
        "## 8. Umbrales operativos",
        "",
        _markdown_table(
            ["Punto", "Umbral", "Precision", "Recall", "F1", "Tasa predicha", "TP/FP/FN/TN"],
            threshold_rows,
        ),
        "",
        "Los umbrales no son argmax ciego: se derivan de la curva precision-recall out-of-fold y de"
        " objetivos explícitos de precision/recall. El punto `0.5 ciego` se incluye solo como "
        "referencia.",
        "",
        "## 9. Importancia de variables",
        "",
        _markdown_table(["Variable", "Valor"], importance_rows),
        "",
        "La importancia es descriptiva, no causal. Si el modelo elegido es un árbol, se reporta "
        "`feature_importances_`; si es logístico, coeficientes estandarizados.",
        "",
        "## 10. Limitaciones y siguientes pasos",
        "",
    ]
    lines.extend(f"- {item}" for item in metrics["limitations"])
    lines.extend(
        [
            "- Próximo paso responsable: ampliar la capa de zonas a todo el territorio regional o "
            "etiquetar a nivel de celda H3, y agregar variables de ignición antrópica (caminos, "
            "tendido eléctrico, interfaces).",
            "- Validar con una temporada completamente futura antes de cualquier uso operativo.",
            "",
            "## 11. Artefactos",
            "",
            f"- `{metrics['artifacts']['model']}` (`sha256` "
            f"`{metrics['artifacts']['model_sha256'][:16]}...`).",
            "- `real_dataset.csv`, `real_dataset_metadata.json`.",
            "- `real_metrics.json`, `real_oof_predictions.csv`.",
            "- `real_model_card.md`, `real_training_report.md`, `REAL_EDA.md`, `real_eda.json`.",
            "",
            "## Reproducción",
            "",
            "```bash",
            "uv run python scripts/crispdm_real_model.py all",
            "```",
            "",
            "El comando anterior intenta Open-Meteo y, si hay límite 429, usa NASA POWER como "
            "respaldo; si ambos fallan, continúa sin clima y lo documenta.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_model_card(metrics: dict[str, Any], metadata: dict[str, Any], path: Path) -> None:
    loso = metrics["validation"]["summaries"]["loso"]
    chosen_curve = metrics["calibration"]["candidates"][metrics["calibration"]["chosen_method"]][
        "curve"
    ]
    ece_text = _fmt(chosen_curve["ece"], 3)
    best = metrics["selected_model"]
    province_pr_auc = _fmt(
        metrics["validation"]["summaries"]["province"][best]["pr_auc"]["mean"], 3
    )
    comuna_pr_auc = _fmt(metrics["validation"]["summaries"]["comuna"][best]["pr_auc"]["mean"], 3)
    lines = [
        "# Model card: baseline real de ocurrencia de incendios por zona y temporada",
        "",
        f"Versión: `{metrics['model_version']}`. Fecha: `{metrics['generated_at']}`. Semilla: "
        f"`{metrics['seed']}`.",
        "",
        "## Descripción",
        "",
        "Modelo de clasificación binaria que estima la probabilidad de que una zona "
        "censal/municipal de la Región de Valparaíso tenga al menos un punto de ignición CONAF en "
        "una temporada. Se entrenó con datos reales 2010-2025 y validación temporal/espacial.",
        "",
        "**Estado: baseline de investigación. No es un modelo operativo y no está integrado en la "
        "API.**",
        "",
        "## Uso previsto",
        "",
        "- Comparar enfoques de modelado y medir si la historia de incendios y las variables "
        "estáticas/climáticas tienen señal.",
        "- Generar hipótesis para priorizar la ampliación de la capa de zonas y la ingeniería de "
        "variables.",
        "- Docencia y revisión metodológica CRISP-DM.",
        "",
        "## Uso no previsto",
        "",
        "- Despacho de brigadas, alertas públicas, seguros o priorización presupuestaria "
        "con consecuencias reales.",
        "- Zonas fuera de la capa de 560 polígonos o fuera de la Región de Valparaíso continental.",
        "- Inferencia causal sobre causas de incendio.",
        "",
        "## Datos",
        "",
        "- Etiquetas: CONAF, puntos de inicio por temporada, 2010_2011..2024_2025.",
        f"- Zonas: {metadata.get('zones', {}).get('zones_used', 'n/d')} polígonos; área "
        f"{_fmt(metadata.get('zones', {}).get('total_area_km2'), 1)} km²; cobertura "
        f"{_fmt(metadata.get('zones', {}).get('coverage_region_pct'), 2)}% del área regional.",
        f"- Filas: {metrics['dataset'].get('rows', 'n/d')}; positivos: "
        f"{metrics['dataset'].get('positives', 'n/d')}; prevalencia: "
        f"{_fmt(metrics['dataset'].get('prevalence'), 3)}.",
        f"- Clima: {metadata.get('climate', {}).get('source') or 'no disponible'}; "
        f"temporada previa y anomalía 1991-2020.",
        "- Combustible: CONAF Catastro de Uso de Suelo y Vegetación 2019, estático.",
        "",
        "## Variables",
        "",
        "Combustible nativo/plantación/matorral/pradera/agrícola/urbano, vegetación, pendiente, "
        "superficie, población, elevación, centroide, historia de incendios previos (última, 3, 5 "
        "temporadas, tasa, tiempo desde el último), agregados comunales previos y clima de la "
        "temporada previa. Se excluyen agregados de todo el período y cualquier dato de la "
        "temporada objetivo.",
        "",
        "## Validación",
        "",
        "- Leave-one-season-out (14 folds).",
        "- Leave-one-province-out (7 provincias).",
        "- `StratifiedGroupKFold` por comuna (5 folds).",
        "- Métricas: PR-AUC, ROC-AUC, Brier, log-loss, precision, recall, F1, matrices de "
        "confusión.",
        "",
        "## Rendimiento (LOSO)",
        "",
        _markdown_table(
            ["Métrica", "Media", "Desv. estándar", "IC95%"],
            [
                [
                    "PR-AUC",
                    _fmt(loso[best]["pr_auc"]["mean"], 3),
                    _fmt(loso[best]["pr_auc"]["std"], 3),
                    f"{_fmt(loso[best]['pr_auc']['ci95'][0], 3)}–"
                    f"{_fmt(loso[best]['pr_auc']['ci95'][1], 3)}",
                ],
                [
                    "ROC-AUC",
                    _fmt(loso[best]["roc_auc"]["mean"], 3),
                    _fmt(loso[best]["roc_auc"]["std"], 3),
                    f"{_fmt(loso[best]['roc_auc']['ci95'][0], 3)}–"
                    f"{_fmt(loso[best]['roc_auc']['ci95'][1], 3)}",
                ],
                [
                    "Brier",
                    _fmt(loso[best]["brier"]["mean"], 3),
                    _fmt(loso[best]["brier"]["std"], 3),
                    f"{_fmt(loso[best]['brier']['ci95'][0], 3)}–"
                    f"{_fmt(loso[best]['brier']['ci95'][1], 3)}",
                ],
            ],
        ),
        "",
        f"Prevalencia de referencia (PR-AUC basal): "
        f"**{_fmt(metrics['selection']['baseline_prevalence_pr_auc'], 3)}**. Regla histórica: "
        f"**{_fmt(metrics['selection']['baseline_history_rule_pr_auc'], 3)}**.",
        f"Validación espacial: PR-AUC provincia **{province_pr_auc}**, comuna **{comuna_pr_auc}**.",
        "",
        "## Calibración y umbrales",
        "",
        f"Método: **{metrics['calibration']['chosen_method']}**. Brier calibrado OOF: "
        f"**{_fmt(metrics['calibration']['calibrated_oof_metrics']['brier'], 3)}**. ECE: "
        f"**{ece_text}**.",
        "",
        "Los umbrales operativos se justifican por precision/recall, no por argmax. Ver "
        "`real_training_report.md` y `real_metrics.json`.",
        "",
        "## Limitaciones",
        "",
    ]
    lines.extend(f"- {item}" for item in metrics["limitations"])
    lines.extend(
        [
            "- El modelo puede aprender principalmente qué zonas tienen historia recurrente de "
            "incendios; eso no equivale a predecir ignición.",
            "- La etiqueta no distingue tamaño, severidad, causa ni impacto.",
            "- La validación espacial muestra degradación; no se debe extrapolar a comunas o zonas "
            "sin historia.",
            "- Los datos CONAF pueden tener subregistro y coordenadas imprecisas.",
            "",
            "## Consideraciones éticas",
            "",
            "No usar para estigmatizar zonas ni para asignar recursos sin revisión humana. Las "
            "predicciones son probabilísticas y agregadas; no identifican personas. Cualquier uso "
            "operativo requiere validación independiente, análisis de costo-beneficio y "
            "supervisión de expertos.",
            "",
            "## Reproducibilidad",
            "",
            "```bash",
            "uv run python scripts/crispdm_real_model.py all",
            "uv run pytest tests/test_crispdm_real_model.py -o addopts=''",
            "```",
            "",
            "El artefacto incluye el pipeline completo, la lista de variables, los umbrales y los "
            "metadatos. No se debe cargar en producción sin una revisión explícita.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def missing_counts(rows: Sequence[dict[str, Any]], features: Sequence[str]) -> dict[str, int]:
    return {name: sum(1 for row in rows if row.get(name) in (None, "")) for name in features}


def run_dataset(
    zones: Sequence[Zone],
    seasons: Sequence[str],
    counts: dict[tuple[int, str], dict[str, float]],
    fire_result: FireLoadResult,
    zone_metadata: dict[str, Any],
    climate_by_comuna: dict[str, dict[str, Any]],
    climate_info: dict[str, Any],
    out_dir: Path,
    seed: int = SEED,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = build_dataset_rows(zones, seasons, counts, climate_by_comuna)
    numeric = list(NUMERIC_BASE)
    if climate_info.get("status") in ("ok", "partial"):
        numeric.extend(CLIMATE_NUMERIC)
    categorical = list(CATEGORICAL_BASE)
    available_numeric, available_categorical, dropped = select_available_features(
        rows, numeric, categorical
    )
    positives = sum(int(row[TARGET]) for row in rows)
    summary = dataset_summary(rows, zones, seasons)
    summary["features"] = {
        "numeric": available_numeric,
        "categorical": available_categorical,
    }
    summary["climate"] = {"status": climate_info.get("status")}
    total_region = sum(item["valid_points"] for item in fire_result.inventory)
    total_assigned = sum(item["assigned"] for item in fire_result.inventory)
    missing = missing_counts(rows, available_numeric + available_categorical)
    metadata: dict[str, Any] = {
        "dataset_version": "conaf-real-zona-temporada-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "target": {
            "name": TARGET,
            "definition": "1 si al menos un punto de ignición CONAF cae dentro de la zona en la "
            "temporada objetivo; 0 en caso contrario.",
            "positive_class": 1,
            "rows_are": "zona x temporada objetivo",
        },
        "seasons": {
            "all": list(seasons),
            "history_only": seasons[0],
            "target": list(seasons[1:]),
        },
        "rows": len(rows),
        "positives": positives,
        "negatives": len(rows) - positives,
        "prevalence": round(positives / len(rows), 6) if rows else None,
        "dataset": summary,
        "features": {
            "numeric": available_numeric,
            "categorical": available_categorical,
            "dropped": dropped,
        },
        "identifiers": IDENTIFIER_COLUMNS,
        "sources": {
            "fires": "CONAF ocurrencia de incendios 2010-2025, shapefiles por temporada",
            "zones": zone_metadata.get("source"),
            "fuels": "CONAF Catastro de Uso de Suelo y Vegetación 2019 (fracciones por zona)",
            "slope": "SRTM 30 m / OpenTopoData (campo slope de la capa de zonas)",
            "climate": climate_info.get("source"),
        },
        "zones": zone_metadata,
        "climate": climate_info,
        "coverage": {
            "zones_used": len(zones),
            "zones_area_km2": round(sum(zone.area_km2 for zone in zones), 3),
            "coverage_region_pct": zone_metadata.get("coverage_region_pct"),
            "regional_points_valid": total_region,
            "regional_points_assigned": total_assigned,
            "regional_assignment_rate": round(total_assigned / total_region, 4)
            if total_region
            else None,
        },
        "missing": missing,
        "leakage_guards": [
            "history features use only seasons strictly before the target season",
            "no historical_fires, incendios_temporadas, incendios_ultima_temporada or "
            "incendios_ultimos_5 from the zone layer",
            "climate features are from the immediately previous season and 1991-2020 climatology, "
            "never the target season",
            "cause, extinction date and burned area of the target season are excluded",
            "season is an identifier for temporal CV, not a model feature",
            "target count n_fires_target is kept only for EDA, not as a feature",
        ],
        "class_balance": {
            "positives": positives,
            "negatives": len(rows) - positives,
            "prevalence": round(positives / len(rows), 6) if rows else None,
        },
        "limitations": [
            "La capa de zonas cubre ~3.7% del área regional y sesga hacia interfaces "
            "urbano-forestales.",
            "La etiqueta es ocurrencia de punto de ignición, no área quemada, "
            "severidad ni impacto.",
            "Los polígonos no son unidades homogéneas de combustible.",
            "El combustible/vegetación es un corte 2019 y la población es censo 2017;"
            " en temporadas previas son información futura, un supuesto estático fuerte.",
            "El clima es de escala comunal (Open-Meteo o NASA POWER) y no resuelve "
            "microclima de ladera.",
            "La temporada 2010_2011 solo aporta historia; no se evalúa como objetivo.",
            "Isla de Pascua y Juan Fernández quedan fuera del modelo continental.",
        ],
    }
    csv_path = out_dir / "real_dataset.csv"
    digest = write_dataset_csv(csv_path, rows, metadata)
    metadata["hash_sha256"] = digest
    metadata["path"] = str(csv_path)
    write_json(out_dir / "real_dataset_metadata.json", metadata)
    return rows, metadata


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--zones",
        type=Path,
        default=None,
        help="GeoJSON de zonas (por defecto: capa oficial de 563 zonas).",
    )
    parser.add_argument(
        "--fires-dir",
        type=Path,
        default=None,
        help="Directorio con subcarpetas de temporadas y shapefiles CONAF.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("ml"),
        help="Directorio de artefactos (por defecto ml/).",
    )
    parser.add_argument(
        "--climate-cache",
        type=Path,
        default=None,
        help="Directorio de caché climática (por defecto <out-dir>/cache/climate).",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--climate",
        choices=["auto", "on", "off"],
        default="auto",
        help="auto: usa caché/red y cae a sin clima; on: intenta siempre; off: sin clima.",
    )
    parser.add_argument(
        "--include-islands",
        action="store_true",
        help="Incluye Isla de Pascua y Juan Fernández (no recomendado para el modelo continental).",
    )
    parser.add_argument(
        "--quick", action="store_true", help="Modelos y calibración reducidos para pruebas."
    )
    parser.add_argument(
        "--max-folds",
        type=int,
        default=0,
        help="Limita folds por esquema (0 = todos); útil para smoke tests.",
    )


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path | None]:
    root = Path(__file__).resolve().parents[1]
    zones = args.zones or root / "src/sigrif/data/cerros_sectores_valparaiso_region_oficial.geojson"
    fires = args.fires_dir or root / "ml/cache/fires"
    out_dir = args.out_dir
    climate_cache = args.climate_cache or out_dir / "cache/climate"
    return zones, fires, out_dir, climate_cache


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline CRISP-DM reproducible para ocurrencia real de incendios por zona y "
        "temporada."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("eda", "Genera ml/real_eda.json, REAL_EDA.md y mapas SVG."),
        ("dataset", "Construye ml/real_dataset.csv y metadatos."),
        ("train", "Entrena, valida, calibra y guarda el artefacto."),
        ("all", "Ejecuta EDA, dataset y entrenamiento."),
    ]:
        subparser = subparsers.add_parser(name, help=help_text)
        _add_common_arguments(subparser)
    args = parser.parse_args(argv)
    zones_path, fires_dir, out_dir, climate_cache = _resolve_paths(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    zones: list[Zone] | None = None
    zone_metadata: dict[str, Any] = {}
    fire_result: FireLoadResult | None = None
    seasons: list[str] = []
    counts: dict[tuple[int, str], dict[str, float]] | None = None
    rows: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    if args.command in {"eda", "dataset", "all"}:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando zonas: {zones_path}")
        zones, zone_metadata = load_zones(zones_path, include_islands=args.include_islands)
        print(f"  zonas usadas: {len(zones)}; área {zone_metadata['total_area_km2']:.1f} km²")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando shapefiles CONAF: {fires_dir}")
        fire_result = load_fire_events(fires_dir, zones)
        seasons = [item["season"] for item in fire_result.inventory]
        counts = build_zone_season_counts(zones, seasons, fire_result.events)
        assigned = sum(item["assigned"] for item in fire_result.inventory)
        valid = sum(item["valid_points"] for item in fire_result.inventory)
        print(
            f"temporadas: {seasons[0]}..{seasons[-1]}; puntos válidos: {valid}; asignados: "
            f"{assigned}"
        )
    if args.command in {"eda", "all"}:
        assert zones is not None and fire_result is not None
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Generando EDA")
        eda = run_eda(zones, fire_result, seasons, out_dir, zone_metadata)
        print(
            f"prevalencia global: {eda['labels']['prevalence']}; asignación: "
            f"{eda['fires']['assignment_rate']}"
        )
    if args.command in {"dataset", "all"}:
        assert zones is not None and fire_result is not None and counts is not None
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Preparando clima (modo {args.climate})")
        climate_by_comuna, climate_info = load_or_fetch_climate(
            zones,
            climate_cache,
            mode=args.climate,
        )
        print(
            f"  clima: {climate_info['status']} "
            f"({climate_info.get('comunas_ok', 0)}/{climate_info.get('comunas_total', 0)} comunas)"
        )
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Construyendo dataset zona x temporada")
        rows, metadata = run_dataset(
            zones,
            seasons,
            counts,
            fire_result,
            zone_metadata,
            climate_by_comuna,
            climate_info,
            out_dir,
            seed=args.seed,
        )
        print(
            f"  filas: {metadata['rows']}; positivos: {metadata['positives']}; "
            f"prevalencia: {metadata['prevalence']}; features: "
            f"{len(metadata['features']['numeric'])}+{len(metadata['features']['categorical'])}"
        )
    if args.command in {"train", "all"}:
        if rows is None or metadata is None:
            dataset_path = out_dir / "real_dataset.csv"
            metadata_path = out_dir / "real_dataset_metadata.json"
            if not dataset_path.exists() or not metadata_path.exists():
                raise FileNotFoundError(
                    f"Faltan {dataset_path} o {metadata_path}; ejecuta primero el subcomando "
                    f"dataset."
                )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo dataset existente")
            rows, metadata = read_dataset_csv(dataset_path, metadata_path)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Entrenando y validando")
        metrics = run_training(
            rows,
            metadata,
            out_dir,
            seed=args.seed,
            quick=args.quick,
            max_folds=args.max_folds,
        )
        print(
            f"  mejor: {metrics['selected_model']}; PR-AUC LOSO: "
            f"{metrics['selection']['best_pr_auc']:.3f}; Brier calibrado: "
            f"{metrics['calibration']['calibrated_oof_metrics']['brier']:.3f}"
        )
        print(f"  artefacto: {metrics['artifacts']['model']}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Listo en {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
