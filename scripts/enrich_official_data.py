"""Enriquece las zonas SIGRIF con datos oficiales de CONAF, incendios y DEM.

El insumo es ``src/sigrif/data/cerros_sectores_valparaiso_region.geojson``.
Los priors academicos de ``vegetation``, ``historical_fires`` y ``slope`` se
reemplazan solo cuando la fuente correspondiente cubre la zona. Cada feature
conserva la procedencia y el estado de cada variable.

Fuentes:
    * CONAF, Catastro de Uso de Suelo y Vegetacion (capa IDE SMA 10), consulta
      por ``CODREG='05'`` paginada y recortada localmente con shapely.
    * CONAF, ocurrencia de incendios por temporada 2010-2011 a 2024-2025,
      publicada por IDE Minagri (puntos de inicio, no area quemada).
    * SRTM 30 m via OpenTopoData para elevaciones y pendiente media aproximada.

Uso:
    uv run python scripts/enrich_official_data.py --source all
    uv run python scripts/enrich_official_data.py --source conaf --limit 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import ssl
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import shapely
from shapely import make_valid
from shapely.geometry import Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "sigrif" / "data"
DEFAULT_INPUT = DATA_DIR / "cerros_sectores_valparaiso_region.geojson"
DEFAULT_OUTPUT = DATA_DIR / "cerros_sectores_valparaiso_region_oficial.geojson"
DEFAULT_CACHE = ROOT / "ml" / "cache"
DEFAULT_REPORT = ROOT / "ml" / "official_data_coverage.json"

CONAF_QUERY_URL = (
    "https://ideserver.sma.gob.cl/arcgis/rest/services/IDE/Biodiversidad/MapServer/10/query"
)
CONAF_LAYER_URL = "https://ideserver.sma.gob.cl/arcgis/rest/services/IDE/Biodiversidad/MapServer/10"
CONAF_WHERE = "CODREG='05'"
CONAF_PAGE_SIZE = 1000
CONAF_SIMPLIFY_DEG = 0.0001
CONAF_FIELDS = "OBJECTID,USO,SUBUSO,SUPERF_HA,NOM_COM,CODREG"

FIRE_URL = (
    "https://ide.minagri.gob.cl/wp-content/uploads/DESCARGAS/CAPAS/DESASTRES/"
    "INCENDIOS_FORESTALES_CONAF/if_temporada_{season}.rar"
)
FIRE_SEASONS = [f"{year}_{year + 1}" for year in range(2010, 2025)]
FIRE_LAST_SEASONS = {"2020_2021", "2021_2022", "2022_2023", "2023_2024", "2024_2025"}

SRTM_URL = "https://api.opentopodata.org/v1/srtm30m"
SRTM_BATCH = 90
SRTM_MIN_INTERVAL = 1.05
DEM_BUFFER_DEG = 0.002
DEM_MAX_POINTS = 16
DEM_PROVIDER = "SRTM 30 m via OpenTopoData"

EARTH_RADIUS_M = 6_378_137.0
UTM_K0 = 0.9996
UTM_LON0 = -69.0


@dataclass
class ConafPolygon:
    """Poligono CONAF ya recortable, con su clasificacion de uso/subuso."""

    object_id: int
    uso: str
    subuso: str
    nom_com: str
    geometry: BaseGeometry


@dataclass
class FirePoint:
    """Punto de inicio de un incendio reportado por CONAF."""

    lon: float
    lat: float
    season: str
    nombre: str = ""
    comuna: str = ""
    causa: str = ""
    fecha: str = ""


@dataclass
class DemSample:
    """Muestras DEM de una zona y el proveedor que las entrego."""

    points: list[tuple[float, float]] = field(default_factory=list)
    elevations: list[float | None] = field(default_factory=list)
    provider: str = DEM_PROVIDER


def lonlat_to_utm_arrays(
    lon: np.ndarray, lat: np.ndarray, lon0: float = UTM_LON0
) -> tuple[np.ndarray, np.ndarray]:
    """Convierte lon/lat WGS84 a UTM 19S usando formulas de Snyder."""

    a = EARTH_RADIUS_M
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    ep2 = e2 / (1.0 - e2)

    phi = np.radians(lat)
    lam = np.radians(lon - lon0)
    sin_phi = np.sin(phi)
    cos_phi = np.cos(phi)
    tan_phi = np.tan(phi)

    n = a / np.sqrt(1.0 - e2 * sin_phi * sin_phi)
    t = tan_phi * tan_phi
    c = ep2 * cos_phi * cos_phi
    aa = cos_phi * lam

    m = a * (
        (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0) * phi
        - (3.0 * e2 / 8.0 + 3.0 * e2**2 / 32.0 + 45.0 * e2**3 / 1024.0) * np.sin(2.0 * phi)
        + (15.0 * e2**2 / 256.0 + 45.0 * e2**3 / 1024.0) * np.sin(4.0 * phi)
        - (35.0 * e2**3 / 3072.0) * np.sin(6.0 * phi)
    )

    east = (
        UTM_K0
        * n
        * (
            aa
            + (1.0 - t + c) * aa**3 / 6.0
            + (5.0 - 18.0 * t + t * t + 72.0 * c - 58.0 * ep2) * aa**5 / 120.0
        )
        + 500_000.0
    )
    north = UTM_K0 * (
        m
        + n
        * tan_phi
        * (
            aa**2 / 2.0
            + (5.0 - t + 9.0 * c + 4.0 * c * c) * aa**4 / 24.0
            + (61.0 - 58.0 * t + t * t + 600.0 * c - 330.0 * ep2) * aa**6 / 720.0
        )
    )
    north = np.where(lat < 0.0, north + 10_000_000.0, north)
    return east, north


def utm_to_lonlat(east: float, north: float, lon0: float = UTM_LON0) -> tuple[float, float]:
    """Convierte UTM 19S a lon/lat WGS84 (formulas inversas de Snyder)."""

    a = EARTH_RADIUS_M
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    ep2 = e2 / (1.0 - e2)

    x = east - 500_000.0
    y = north - 10_000_000.0
    mu = y / (UTM_K0 * a * (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0))
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
        + (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu)
    )
    sin1 = math.sin(phi1)
    cos1 = math.cos(phi1)
    tan1 = math.tan(phi1)
    n1 = a / math.sqrt(1.0 - e2 * sin1 * sin1)
    t1 = tan1 * tan1
    c1 = ep2 * cos1 * cos1
    r1 = a * (1.0 - e2) / (1.0 - e2 * sin1 * sin1) ** 1.5
    d = x / (n1 * UTM_K0)

    phi = phi1 - (n1 * tan1 / r1) * (
        d**2 / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * ep2) * d**4 / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 * t1 - 252.0 * ep2 - 3.0 * c1 * c1)
        * d**6
        / 720.0
    )
    lam = (
        d
        - (1.0 + 2.0 * t1 + c1) * d**3 / 6.0
        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 * c1 + 8.0 * ep2 + 24.0 * t1 * t1) * d**5 / 120.0
    ) / cos1
    return lon0 + math.degrees(lam), math.degrees(phi)


def project_geometry(geom: BaseGeometry, lon0: float = UTM_LON0) -> BaseGeometry:
    """Proyecta una geometria lon/lat a UTM 19S."""

    def _project(coords: np.ndarray) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        east, north = lonlat_to_utm_arrays(arr[:, 0], arr[:, 1], lon0)
        return np.column_stack([east, north])

    return shapely.transform(geom, _project)


def rings_to_geometry(rings: Sequence[Sequence[Sequence[float]]]) -> BaseGeometry:
    """Convierte los ``rings`` de ArcGIS a un Polygon/MultiPolygon valido."""

    polygons: list[BaseGeometry] = []
    for ring in rings:
        coords = [(float(x), float(y)) for x, y in ring]
        if len(coords) < 4:
            continue
        polygon = Polygon(coords)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        if polygon.is_empty or polygon.area <= 0:
            continue
        polygons.append(polygon)

    if not polygons:
        return Polygon()
    if len(polygons) == 1:
        return polygons[0]

    polygons.sort(key=lambda item: item.area, reverse=True)
    shells: list[BaseGeometry] = []
    holes: list[BaseGeometry] = []
    for polygon in polygons:
        point = polygon.representative_point()
        if any(shell.contains(point) for shell in shells):
            holes.append(polygon)
        else:
            shells.append(polygon)

    geometry = unary_union(shells)
    if holes:
        geometry = geometry.difference(unary_union(holes))
    return geometry


def _polygonal(geom: BaseGeometry) -> BaseGeometry:
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom
    parts = [
        part for part in getattr(geom, "geoms", []) if part.geom_type in {"Polygon", "MultiPolygon"}
    ]
    return unary_union(parts) if parts else Polygon()


def _normalize(text: str) -> str:
    import unicodedata

    value = unicodedata.normalize("NFKD", str(text or ""))
    value = value.encode("ascii", "ignore").decode("ascii")
    return " ".join(value.lower().split())


CATEGORY_WEIGHTS: dict[tuple[str, str], dict[str, float]] = {
    ("bosques", "bosque nativo"): {"bosque_nativo": 1.0},
    ("bosques", "bosque mixto"): {"bosque_mixto": 1.0},
    ("bosques", "plantacion"): {"plantacion": 1.0},
    ("praderas y matorrales", "matorral"): {"matorral": 1.0},
    ("praderas y matorrales", "matorral arborescente"): {"matorral": 1.0},
    ("praderas y matorrales", "matorral con suculentas"): {"matorral": 1.0},
    ("praderas y matorrales", "formacion de suculentas"): {"matorral": 1.0},
    ("praderas y matorrales", "matorral-pradera"): {"matorral": 0.5, "pradera": 0.5},
    ("praderas y matorrales", "praderas"): {"pradera": 1.0},
    ("terrenos agricolas", "terreno de uso agricola"): {"agricola": 1.0},
    ("terrenos agricolas", "rotacion cultivo-pradera"): {"agricola": 0.5, "pradera": 0.5},
    ("areas urbanas e industriales", "ciudades, pueblos, zonas industriales"): {"urbano": 1.0},
    ("areas urbanas e industriales", "mineria industrial"): {"urbano": 1.0},
    ("cuerpos de agua", "rios"): {"agua": 1.0},
    ("cuerpos de agua", "lagos, lagunas, embalses, tranques"): {"agua": 1.0},
    ("humedales", "vegas"): {"humedal": 1.0},
    ("humedales", "otros terrenos humedos"): {"humedal": 1.0},
    ("humedales", "vegetacion herbacea en orillas de rios"): {"humedal": 1.0},
    ("areas desprovistas de vegetacion", "afloramientos rocosos"): {"desprovisto": 1.0},
    ("areas desprovistas de vegetacion", "cajas de rios"): {"desprovisto": 1.0},
    ("areas desprovistas de vegetacion", "derrumbe sin vegetacion"): {"desprovisto": 1.0},
    ("areas desprovistas de vegetacion", "otros sin vegetacion"): {"desprovisto": 1.0},
    ("areas desprovistas de vegetacion", "playas y dunas"): {"desprovisto": 1.0},
    (
        "areas desprovistas de vegetacion",
        "terrenos sobre el limite altitudinal de la vegetacion",
    ): {"desprovisto": 1.0},
    ("nieves eternas y glaciares", "glaciares"): {"nieve": 1.0},
    ("nieves eternas y glaciares", "nieves"): {"nieve": 1.0},
}

VEGETATION_CATEGORIES = ("bosque_nativo", "bosque_mixto", "plantacion", "matorral")
ALL_CATEGORIES = (
    "bosque_nativo",
    "bosque_mixto",
    "plantacion",
    "matorral",
    "pradera",
    "agricola",
    "urbano",
    "agua",
    "humedal",
    "desprovisto",
    "nieve",
    "otro",
)


def category_weights(uso: str, subuso: str) -> dict[str, float]:
    """Devuelve el reparto de un poligono CONAF entre categorias."""

    key = (_normalize(uso), _normalize(subuso))
    return CATEGORY_WEIGHTS.get(key, {"otro": 1.0})


def make_http_client(timeout: float = 60.0) -> httpx.Client:
    """Cliente con CA del sistema; el bundle de certifi no siempre basta."""

    context = ssl.create_default_context()
    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=15.0),
        verify=context,
        follow_redirects=True,
        headers={"User-Agent": "SIGRIF-academic/1.0"},
    )


def request_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    attempts: int = 4,
    backoff: float = 1.5,
) -> dict[str, Any]:
    """GET con reintentos y errores explicitos."""

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("respuesta JSON inesperada")
            if payload.get("error"):
                raise RuntimeError(f"servicio remoto: {payload['error']}")
            return payload
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(backoff**attempt)
    raise RuntimeError(f"fallo al consultar {url}: {last_error}")


def _write_json_atomic(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    separators = (",", ":") if compact else None
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, separators=separators),
        encoding="utf-8",
    )
    tmp.replace(path)


def _conaf_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "conaf" / "valparaiso_uso_suelo.geojson"


def _conaf_from_geojson(payload: dict[str, Any]) -> list[ConafPolygon]:
    polygons: list[ConafPolygon] = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if not geometry:
            continue
        geom = _polygonal(make_valid(shape(geometry)))
        if geom.is_empty:
            continue
        polygons.append(
            ConafPolygon(
                object_id=int(props.get("OBJECTID") or 0),
                uso=str(props.get("USO") or ""),
                subuso=str(props.get("SUBUSO") or ""),
                nom_com=str(props.get("NOM_COM") or ""),
                geometry=geom,
            )
        )
    return polygons


def load_conaf_region(
    client: httpx.Client,
    cache_dir: Path,
    *,
    refresh: bool = False,
    log: Any = print,
) -> list[ConafPolygon]:
    """Descarga (o lee de cache) el catastro CONAF de la Region de Valparaiso."""

    cache_path = _conaf_cache_path(cache_dir)
    if cache_path.exists() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        polygons = _conaf_from_geojson(payload)
        log(f"CONAF: {len(polygons)} poligonos desde cache {cache_path}")
        return polygons

    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": CONAF_WHERE,
            "outFields": CONAF_FIELDS,
            "returnGeometry": "true",
            "geometryPrecision": 5,
            "maxAllowableOffset": CONAF_SIMPLIFY_DEG,
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": CONAF_PAGE_SIZE,
            "f": "json",
        }
        payload = request_json(client, CONAF_QUERY_URL, params=params)
        batch = payload.get("features") or []
        for feature in batch:
            props = feature.get("attributes") or {}
            rings = (feature.get("geometry") or {}).get("rings") or []
            geometry = _polygonal(rings_to_geometry(rings))
            if geometry.is_empty:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": mapping(geometry),
                    "properties": {
                        "OBJECTID": int(props.get("OBJECTID") or 0),
                        "USO": str(props.get("USO") or ""),
                        "SUBUSO": str(props.get("SUBUSO") or ""),
                        "SUPERF_HA": props.get("SUPERF_HA"),
                        "NOM_COM": str(props.get("NOM_COM") or ""),
                    },
                }
            )
        offset += len(batch)
        log(f"CONAF: {offset} poligonos descargados")
        if not payload.get("exceededTransferLimit") or not batch:
            break

    payload = {
        "type": "FeatureCollection",
        "name": "conaf_uso_suelo_valparaiso",
        "features": features,
        "metadata": {
            "fuente": CONAF_LAYER_URL,
            "where": CONAF_WHERE,
            "fecha_consulta": datetime.now(UTC).date().isoformat(),
            "maxAllowableOffset_deg": CONAF_SIMPLIFY_DEG,
        },
    }
    _write_json_atomic(cache_path, payload, compact=True)
    polygons = _conaf_from_geojson(payload)
    log(f"CONAF: {len(polygons)} poligonos en cache {cache_path}")
    return polygons


def conaf_fractions(
    zone_geometry: BaseGeometry,
    polygons: Sequence[ConafPolygon],
    tree: STRtree | None = None,
) -> dict[str, float] | None:
    """Calcula fracciones de uso de suelo recortando cada poligono a la zona.

    Devuelve ``None`` si ningun poligono CONAF intersecta la zona. Las areas se
    calculan en UTM 19S; si la suma de categorias excede la zona (solapamientos
    o geometrias simplificadas) se normaliza para que no supere 1.
    """

    if not polygons:
        return None

    zone_utm = project_geometry(zone_geometry)
    zone_area = zone_utm.area
    if zone_area <= 0:
        return None

    candidates: Iterable[int]
    if tree is not None:
        candidates = (int(index) for index in tree.query(zone_geometry))
    else:
        candidates = range(len(polygons))

    raw_areas = dict.fromkeys(ALL_CATEGORIES, 0.0)
    used = 0
    for index in candidates:
        polygon = polygons[index]
        if not polygon.geometry.intersects(zone_geometry):
            continue
        polygon_utm = project_geometry(polygon.geometry)
        intersection = polygon_utm.intersection(zone_utm)
        if intersection.is_empty:
            continue
        area = intersection.area
        if area <= 0:
            continue
        used += 1
        for category, weight in category_weights(polygon.uso, polygon.subuso).items():
            raw_areas[category] += area * weight

    total = sum(raw_areas.values())
    if used == 0 or total <= 0:
        return None

    scale = min(1.0, zone_area / total)
    fractions = {key: value * scale / zone_area for key, value in raw_areas.items()}
    fractions["cobertura"] = min(1.0, total / zone_area)
    fractions["poligonos"] = float(used)
    return fractions


def _extract_rar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    seven = shutil.which("7z") or shutil.which("7za")
    if seven:
        command = [seven, "x", "-y", f"-o{destination}", str(archive)]
    elif shutil.which("unrar"):
        command = [shutil.which("unrar") or "unrar", "x", "-y", str(archive), str(destination)]
    elif shutil.which("bsdtar"):
        command = [shutil.which("bsdtar") or "bsdtar", "-xf", str(archive), "-C", str(destination)]
    else:
        raise RuntimeError("no hay extractor .rar (7z, unrar o bsdtar)")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"no se pudo extraer {archive}: {result.stderr.strip()}")


def _field(record: dict[str, Any], *names: str) -> str:
    lower = {str(key).lower(): value for key, value in record.items()}
    for name in names:
        value = lower.get(name.lower())
        if value is not None:
            return str(value).strip()
    return ""


def _read_fire_shapefile(path: Path, season: str) -> list[FirePoint]:
    import shapefile

    prj_path = path.with_suffix(".prj")
    prj = prj_path.read_text(encoding="utf-8", errors="ignore") if prj_path.exists() else ""
    is_utm = "PROJCS" in prj and "19S" in prj
    is_geographic = "GEOGCS" in prj and not is_utm
    if not (is_utm or is_geographic):
        raise RuntimeError(f"proyeccion no reconocida en {prj_path}")

    reader = shapefile.Reader(str(path), encoding="utf-8")
    points: list[FirePoint] = []
    for shape_record in reader.iterShapeRecords():
        geometry = shape_record.shape
        if geometry.shapeType == 0 or not geometry.points:
            continue
        x, y = geometry.points[0]
        if is_utm:
            lon, lat = utm_to_lonlat(float(x), float(y))
        else:
            lon, lat = float(x), float(y)
        if not (-72.5 <= lon <= -69.5 and -34.5 <= lat <= -31.5):
            continue
        record = shape_record.record.as_dict()
        points.append(
            FirePoint(
                lon=lon,
                lat=lat,
                season=season,
                nombre=_field(record, "NOM_INCEN", "NOMBRE"),
                comuna=_field(record, "COMUNA"),
                causa=_field(record, "CAUSA_GENE"),
                fecha=_field(record, "INICIO_C", "INICIO_CER"),
            )
        )
    reader.close()
    return points


def _fires_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "fires" / "incendios_valparaiso_2010_2025.geojson"


def load_fire_points(
    client: httpx.Client,
    cache_dir: Path,
    *,
    refresh: bool = False,
    log: Any = print,
) -> list[FirePoint]:
    """Descarga las temporadas CONAF y devuelve puntos de inicio en la region."""

    cache_path = _fires_cache_path(cache_dir)
    if cache_path.exists() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_points = [
            FirePoint(
                lon=float(feature["geometry"]["coordinates"][0]),
                lat=float(feature["geometry"]["coordinates"][1]),
                season=str(feature["properties"].get("temporada") or ""),
                nombre=str(feature["properties"].get("nombre") or ""),
                comuna=str(feature["properties"].get("comuna") or ""),
                causa=str(feature["properties"].get("causa") or ""),
                fecha=str(feature["properties"].get("fecha") or ""),
            )
            for feature in payload.get("features", [])
        ]
        log(f"Incendios: {len(cached_points)} puntos desde cache {cache_path}")
        return cached_points

    points: list[FirePoint] = []
    fires_dir = cache_dir / "fires"
    fires_dir.mkdir(parents=True, exist_ok=True)
    for season in FIRE_SEASONS:
        season_dir = fires_dir / season
        rar_path = fires_dir / f"if_temporada_{season}.rar"
        if not rar_path.exists():
            log(f"Incendios: descargando temporada {season}")
            last_error: Exception | None = None
            for attempt in range(4):
                try:
                    response = client.get(FIRE_URL.format(season=season))
                    response.raise_for_status()
                    rar_path.write_bytes(response.content)
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt == 3:
                        raise
                    time.sleep(1.5**attempt)
            if last_error and not rar_path.exists():
                raise RuntimeError(f"no se pudo descargar {season}: {last_error}")
        if not season_dir.exists():
            _extract_rar(rar_path, season_dir)
        shapefiles = list(season_dir.glob("*.shp"))
        if not shapefiles:
            raise RuntimeError(f"no se encontro .shp para {season}")
        points.extend(_read_fire_shapefile(shapefiles[0], season))
        log(f"Incendios: temporada {season} -> {len(points)} puntos regionales")

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [point.lon, point.lat]},
            "properties": {
                "temporada": point.season,
                "nombre": point.nombre,
                "comuna": point.comuna,
                "causa": point.causa,
                "fecha": point.fecha,
            },
        }
        for point in points
    ]
    payload = {
        "type": "FeatureCollection",
        "name": "incendios_valparaiso_2010_2025",
        "features": features,
        "metadata": {
            "fuente": "CONAF / IDE Minagri, ocurrencia de incendios",
            "temporadas": FIRE_SEASONS,
            "fecha_consulta": datetime.now(UTC).date().isoformat(),
        },
    }
    _write_json_atomic(cache_path, payload, compact=True)
    log(f"Incendios: {len(points)} puntos en cache {cache_path}")
    return points


def count_fires_by_zone(
    zones: Sequence[BaseGeometry], points: Sequence[FirePoint]
) -> tuple[list[int], list[int], list[str | None], list[int]]:
    """Cuenta puntos de incendio por zona y temporadas con al menos un evento."""

    tree = STRtree(zones)
    counts = [0] * len(zones)
    seasons: list[set[str]] = [set() for _ in zones]
    last_five = [0] * len(zones)

    for fire in points:
        point = Point(fire.lon, fire.lat)
        for raw_index in tree.query(point):
            index = int(raw_index)
            if not zones[index].covers(point):
                continue
            counts[index] += 1
            seasons[index].add(fire.season)
            if fire.season in FIRE_LAST_SEASONS:
                last_five[index] += 1

    latest = [max(season_set) if season_set else None for season_set in seasons]
    return counts, [len(season_set) for season_set in seasons], latest, last_five


def _grid_points(area: BaseGeometry, divisions: int) -> list[tuple[float, float]]:
    minx, miny, maxx, maxy = area.bounds
    dx = (maxx - minx) / divisions
    dy = (maxy - miny) / divisions
    points: list[tuple[float, float]] = []
    for row in range(divisions):
        for col in range(divisions):
            point = Point(minx + (col + 0.5) * dx, miny + (row + 0.5) * dy)
            if area.covers(point):
                points.append((point.x, point.y))
    return points


def sample_zone_points(
    geometry: BaseGeometry, max_points: int = DEM_MAX_POINTS
) -> list[tuple[float, float]]:
    """Genera una grilla de muestras; usa un buffer de ~200 m si hace falta.

    Las zonas urbanas miden decenas de metros y el DEM SRTM tiene ~30 m de
    resolucion. Para que el plano local tenga sentido se muestrea el entorno
    inmediato (buffer 0.002 grados) cuando la zona es pequena o cuando su
    geometria es tan estrecha que la grilla interna deja menos de 6 puntos.
    """

    minx, miny, maxx, maxy = geometry.bounds
    span = max(maxx - minx, maxy - miny)
    if span < 0.006:
        candidates = _grid_points(geometry.buffer(DEM_BUFFER_DEG), 5)
    else:
        candidates = _grid_points(geometry, 5)
        if len(candidates) < 6:
            candidates = _grid_points(geometry, 8)
        if len(candidates) < 6:
            candidates = _grid_points(geometry.buffer(DEM_BUFFER_DEG), 5)
        if len(candidates) < 6:
            candidates = _grid_points(geometry.buffer(DEM_BUFFER_DEG), 8)

    if len(candidates) <= max_points:
        return candidates
    selected = np.linspace(0, len(candidates) - 1, max_points).round().astype(int)
    return [candidates[index] for index in selected]


def _dem_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "dem" / "srtm_samples.json"


def _zone_key(geometry: BaseGeometry) -> str:
    return hashlib.sha1(shapely.to_wkb(geometry)).hexdigest()[:16]


def _fetch_dem_batch(
    client: httpx.Client, points: Sequence[tuple[float, float]]
) -> list[float | None]:
    locations = "|".join(f"{lat:.6f},{lon:.6f}" for lon, lat in points)
    payload = request_json(client, SRTM_URL, params={"locations": locations})
    results = payload.get("results") or []
    if len(results) != len(points):
        raise RuntimeError(f"SRTM devolvio {len(results)} resultados para {len(points)} puntos")
    elevations: list[float | None] = []
    for result in results:
        value = result.get("elevation")
        elevations.append(float(value) if value is not None else None)
    return elevations


def load_dem_samples(
    client: httpx.Client,
    zones: Sequence[BaseGeometry],
    cache_dir: Path,
    *,
    refresh: bool = False,
    log: Any = print,
) -> dict[str, DemSample]:
    """Muestrea elevaciones SRTM para cada zona, con cache y fallback por lote."""

    cache_path = _dem_cache_path(cache_dir)
    cached: dict[str, Any] = {}
    if cache_path.exists() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        cached = payload.get("zonas") or {}

    samples: dict[str, DemSample] = {}
    pending: list[tuple[str, list[tuple[float, float]]]] = []
    for geometry in zones:
        key = _zone_key(geometry)
        if key in cached:
            entry = cached[key]
            cached_points = [(float(lon), float(lat)) for lon, lat in entry.get("points", [])]
            if cached_points:
                samples[key] = DemSample(
                    points=cached_points,
                    elevations=entry.get("elevations", []),
                    provider=str(entry.get("provider") or DEM_PROVIDER),
                )
                continue
        pending.append((key, sample_zone_points(geometry)))

    total_points = sum(len(points) for _, points in pending)
    log(f"DEM: {len(pending)} zonas pendientes, {total_points} puntos por consultar")

    for start in range(0, total_points, SRTM_BATCH):
        batch: list[tuple[str, int, tuple[float, float]]] = []
        for key, points in pending:
            for index, point in enumerate(points):
                batch.append((key, index, point))
        batch = batch[start : start + SRTM_BATCH]
        try:
            elevations = _fetch_dem_batch(client, [item[2] for item in batch])
        except Exception as exc:
            log(f"DEM: fallo de lote en offset {start}: {exc}")
            for key, _index, _point in batch:
                samples.setdefault(key, DemSample())
            time.sleep(SRTM_MIN_INTERVAL)
            continue

        for (key, index, point), elevation in zip(batch, elevations, strict=True):
            sample = samples.setdefault(key, DemSample())
            while len(sample.points) <= index:
                sample.points.append((0.0, 0.0))
                sample.elevations.append(None)
            sample.points[index] = point
            sample.elevations[index] = elevation
        time.sleep(SRTM_MIN_INTERVAL)

    all_zones = dict(cached)
    for key, sample in samples.items():
        if not sample.points:
            continue
        all_zones[key] = {
            "points": sample.points,
            "elevations": sample.elevations,
            "provider": sample.provider,
        }
    payload = {
        "provider": DEM_PROVIDER,
        "fecha_consulta": datetime.now(UTC).date().isoformat(),
        "zonas": all_zones,
    }
    _write_json_atomic(cache_path, payload)
    log(f"DEM: {len(samples)} zonas muestreadas")
    return samples


def slope_from_samples(
    points: Sequence[tuple[float, float]], elevations: Sequence[float | None]
) -> float | None:
    """Ajusta un plano local z=a*x+b*y+c y devuelve la pendiente en grados."""

    valid = [
        (lon, lat, float(elevation))
        for (lon, lat), elevation in zip(points, elevations, strict=False)
        if elevation is not None
    ]
    if len(valid) < 3:
        return None

    lon0 = sum(point[0] for point in valid) / len(valid)
    east, north = lonlat_to_utm_arrays(
        np.array([point[0] for point in valid]),
        np.array([point[1] for point in valid]),
        lon0,
    )
    x = east - east.mean()
    y = north - north.mean()
    z = np.array([point[2] for point in valid], dtype=float)
    design = np.column_stack([x, y, np.ones(len(valid))])
    coefficients, *_ = np.linalg.lstsq(design, z, rcond=None)
    gradient = math.hypot(float(coefficients[0]), float(coefficients[1]))
    return math.degrees(math.atan(gradient))


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _priority_props(properties: dict[str, Any]) -> tuple[float, int, float]:
    return (
        _as_float(properties.get("vegetation"), 0.30),
        _as_int(properties.get("historical_fires"), 0),
        _as_float(properties.get("slope"), 15.0),
    )


def enrich_features(
    features: Sequence[dict[str, Any]],
    *,
    source: str,
    updated: str,
    conaf_polygons: Sequence[ConafPolygon] | None = None,
    fire_points: Sequence[FirePoint] | None = None,
    dem_samples: dict[str, DemSample] | None = None,
    workers: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aplica las fuentes disponibles y devuelve features + metricas de cobertura."""

    geometries = [shape(feature["geometry"]) for feature in features]
    conaf_tree = (
        STRtree([polygon.geometry for polygon in conaf_polygons]) if conaf_polygons else None
    )
    fire_counts: list[int] | None = None
    fire_season_counts: list[int] | None = None
    fire_latest: list[str | None] | None = None
    fire_last_five: list[int] | None = None
    if source in {"all", "fires"} and fire_points is not None:
        fire_counts, fire_season_counts, fire_latest, fire_last_five = count_fires_by_zone(
            geometries, fire_points
        )

    def _cover(index: int) -> dict[str, float] | None:
        if source not in {"all", "conaf"} or conaf_polygons is None:
            return None
        return conaf_fractions(geometries[index], conaf_polygons, conaf_tree)

    covers: list[dict[str, float] | None]
    if workers > 1 and len(features) > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            covers = list(executor.map(_cover, range(len(features))))
    else:
        covers = [_cover(index) for index in range(len(features))]

    result: list[dict[str, Any]] = []
    stats = {
        "zonas": len(features),
        "conaf_con_cobertura": 0,
        "conaf_sin_cobertura": 0,
        "conaf_cobertura_media": 0.0,
        "incendios_zonas_con_eventos": 0,
        "incendios_zonas_sin_eventos": 0,
        "incendios_asignados": 0,
        "incendios_pendientes": 0,
        "dem_con_pendiente": 0,
        "dem_fallback": 0,
        "dem_pendientes": 0,
        "dem_puntos": 0,
        "dem_puntos_invalidos": 0,
    }
    coverage_values: list[float] = []

    for index, feature in enumerate(features):
        properties = dict(feature.get("properties") or {})
        prior_vegetation, prior_fires, prior_slope = _priority_props(properties)
        properties.setdefault("vegetation", prior_vegetation)
        properties.setdefault("historical_fires", prior_fires)
        properties.setdefault("slope", prior_slope)
        properties["vegetation_prior"] = round(prior_vegetation, 6)
        properties["historical_fires_prior"] = prior_fires
        properties["slope_prior"] = round(prior_slope, 6)

        if source in {"all", "conaf"}:
            cover = covers[index] if conaf_polygons else None
            if cover is None:
                properties["vegetation"] = round(prior_vegetation, 6)
                properties["Estado_Vegetacion"] = "pendiente"
                if conaf_polygons is None:
                    properties["Fuente_Vegetacion"] = (
                        "prior academico; fuente CONAF no disponible en esta ejecucion"
                    )
                else:
                    properties["Fuente_Vegetacion"] = "prior academico; sin cobertura CONAF"
                properties["conaf_cobertura_frac"] = 0.0
                properties["conaf_poligonos"] = 0
                stats["conaf_sin_cobertura"] += 1
            else:
                vegetation = min(
                    1.0, sum(cover.get(category, 0.0) for category in VEGETATION_CATEGORIES)
                )
                properties["vegetation"] = round(vegetation, 6)
                for category in ALL_CATEGORIES:
                    properties[f"veg_{category}_frac"] = round(cover.get(category, 0.0), 6)
                properties["conaf_cobertura_frac"] = round(cover.get("cobertura", 0.0), 6)
                properties["conaf_poligonos"] = int(cover.get("poligonos", 0))
                properties["Estado_Vegetacion"] = "oficial"
                properties["Fuente_Vegetacion"] = (
                    "CONAF Catastro de Uso de Suelo y Vegetacion 2019 "
                    "(IDE SMA, capa Biodiversidad/10)"
                )
                if cover.get("cobertura", 0.0) < 0.90:
                    properties["Nota_Vegetacion"] = "cobertura CONAF parcial (<90% de la zona)"
                stats["conaf_con_cobertura"] += 1
                stats["conaf_cobertura_media"] += cover.get("cobertura", 0.0)
                coverage_values.append(cover.get("cobertura", 0.0))

        if source in {"all", "fires"}:
            if fire_counts is None:
                properties["historical_fires"] = prior_fires
                properties["Estado_Incendios"] = "pendiente"
                properties["Fuente_Incendios"] = (
                    "prior academico; fuente de incendios no disponible en esta ejecucion"
                )
                stats["incendios_pendientes"] += 1
            else:
                count = fire_counts[index]
                properties["historical_fires"] = count
                properties["incendios_temporadas"] = (
                    fire_season_counts[index] if fire_season_counts else 0
                )
                properties["incendios_ultima_temporada"] = (
                    fire_latest[index] if fire_latest else None
                )
                properties["incendios_ultimos_5"] = fire_last_five[index] if fire_last_five else 0
                properties["Estado_Incendios"] = "oficial"
                properties["Fuente_Incendios"] = (
                    "CONAF ocurrencia de incendios 2010-2025 (IDE Minagri, puntos de inicio)"
                )
                if count > 0:
                    stats["incendios_zonas_con_eventos"] += 1
                else:
                    stats["incendios_zonas_sin_eventos"] += 1
                stats["incendios_asignados"] += count

        if source in {"all", "dem"}:
            if dem_samples is None:
                properties["slope"] = round(prior_slope, 6)
                properties["Estado_Pendiente"] = "pendiente"
                properties["Fuente_Pendiente"] = (
                    "prior academico; DEM no disponible en esta ejecucion"
                )
                stats["dem_pendientes"] += 1
                stats["dem_fallback"] += 1
            else:
                sample = dem_samples.get(_zone_key(geometries[index]))
                slope = None
                if sample is not None and sample.points:
                    valid_points: list[tuple[float, float]] = []
                    valid_elevations: list[float] = []
                    for point, elevation in zip(sample.points, sample.elevations, strict=False):
                        if elevation is None:
                            continue
                        if not geometries[index].covers(Point(point)) and elevation <= 0.0:
                            continue
                        valid_points.append(point)
                        valid_elevations.append(elevation)
                    slope = slope_from_samples(valid_points, valid_elevations)
                    properties["dem_muestras"] = len(valid_points)
                    properties["dem_muestras_totales"] = len(sample.points)
                    properties["dem_puntos_invalidos"] = len(sample.points) - len(valid_points)
                    stats["dem_puntos"] += len(sample.points)
                    stats["dem_puntos_invalidos"] += len(sample.points) - len(valid_points)
                    if valid_elevations:
                        properties["dem_elev_media_m"] = round(
                            sum(valid_elevations) / len(valid_elevations), 1
                        )
                        properties["dem_elev_min_m"] = round(min(valid_elevations), 1)
                        properties["dem_elev_max_m"] = round(max(valid_elevations), 1)
                    properties["dem_proveedor"] = sample.provider
                if slope is None:
                    properties["slope"] = round(prior_slope, 6)
                    properties["Estado_Pendiente"] = "pendiente"
                    properties["Fuente_Pendiente"] = "prior academico; DEM sin muestras suficientes"
                    stats["dem_fallback"] += 1
                else:
                    properties["slope"] = round(min(89.0, max(0.0, slope)), 6)
                    properties["Estado_Pendiente"] = "oficial_aproximado"
                    properties["Fuente_Pendiente"] = (
                        "SRTM 30 m via OpenTopoData; plano local ajustado por zona"
                    )
                    stats["dem_con_pendiente"] += 1

        if source != "all":
            if "Fuente_Incendios" not in properties:
                properties["Fuente_Incendios"] = "no consultado en esta ejecucion"
                properties.setdefault("Estado_Incendios", "pendiente")
            if "Fuente_Pendiente" not in properties:
                properties["Fuente_Pendiente"] = "no consultado en esta ejecucion"
                properties.setdefault("Estado_Pendiente", "pendiente")
            if "Fuente_Vegetacion" not in properties:
                properties["Fuente_Vegetacion"] = "no consultado en esta ejecucion"
                properties.setdefault("Estado_Vegetacion", "pendiente")

        properties["Datos_Actualizados"] = updated
        result.append(
            {
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": properties,
            }
        )

    if stats["conaf_con_cobertura"]:
        stats["conaf_cobertura_media"] = round(
            stats["conaf_cobertura_media"] / stats["conaf_con_cobertura"], 6
        )
    if coverage_values:
        stats["conaf_cobertura_mediana"] = round(float(np.median(coverage_values)), 6)
    return result, stats


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enriquece zonas SIGRIF con CONAF, incendios y DEM."
    )
    parser.add_argument(
        "--source",
        choices=["all", "conaf", "fires", "dem"],
        default="all",
        help="fuente a actualizar (default: all)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="procesar solo las primeras N zonas"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="GeoJSON de entrada")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="GeoJSON de salida")
    parser.add_argument("--workers", type=int, default=4, help="hilos para el recorte CONAF")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="cache de descargas")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="reporte de cobertura")
    parser.add_argument("--refresh", action="store_true", help="ignorar cache y reconsultar")
    parser.add_argument("--strict", action="store_true", help="fallar si una fuente no responde")
    return parser.parse_args(argv)


def _load_features(path: Path, limit: int | None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = list(payload.get("features", []))
    if limit is not None:
        features = features[: max(0, limit)]
    return features


def _samples(features: Sequence[dict[str, Any]], count: int = 6) -> list[dict[str, Any]]:
    """Selecciona una muestra variada: primeras zonas y extremos de cada variable."""

    selected: list[dict[str, Any]] = list(features[:3])
    for key in ("vegetation", "historical_fires", "slope"):
        best = max(features, key=lambda feature: feature["properties"].get(key, 0) or 0)
        if best not in selected:
            selected.append(best)
    if len(selected) < count:
        for feature in features:
            if feature not in selected:
                selected.append(feature)
            if len(selected) >= count:
                break

    samples = []
    for feature in selected[:count]:
        props = feature.get("properties") or {}
        samples.append(
            {
                "Nombre_Cer": props.get("Nombre_Cer"),
                "Comuna": props.get("Comuna"),
                "Nivel": props.get("Nivel"),
                "vegetation": props.get("vegetation"),
                "historical_fires": props.get("historical_fires"),
                "slope": props.get("slope"),
                "conaf_cobertura_frac": props.get("conaf_cobertura_frac"),
                "conaf_poligonos": props.get("conaf_poligonos"),
                "incendios_temporadas": props.get("incendios_temporadas"),
                "dem_muestras": props.get("dem_muestras"),
                "Estado_Vegetacion": props.get("Estado_Vegetacion"),
                "Estado_Incendios": props.get("Estado_Incendios"),
                "Estado_Pendiente": props.get("Estado_Pendiente"),
            }
        )
    return samples


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    started = datetime.now(UTC)
    updated = started.date().isoformat()
    features = _load_features(args.input, args.limit)
    if not features:
        print("No hay features para procesar", file=sys.stderr)
        return 2

    print(f"Zonas de entrada: {len(features)} ({args.input})")
    client = make_http_client()
    source_errors: dict[str, str] = {}
    conaf_polygons: list[ConafPolygon] | None = None
    fire_points: list[FirePoint] | None = None
    dem_samples: dict[str, DemSample] | None = None

    try:
        if args.source in {"all", "conaf"}:
            try:
                conaf_polygons = load_conaf_region(client, args.cache_dir, refresh=args.refresh)
            except Exception as exc:
                source_errors["conaf"] = str(exc)
                print(f"CONAF no disponible: {exc}", file=sys.stderr)
                if args.strict:
                    raise
        if args.source in {"all", "fires"}:
            try:
                fire_points = load_fire_points(client, args.cache_dir, refresh=args.refresh)
            except Exception as exc:
                source_errors["incendios"] = str(exc)
                print(f"Incendios no disponibles: {exc}", file=sys.stderr)
                if args.strict:
                    raise
        if args.source in {"all", "dem"}:
            try:
                geometries = [shape(feature["geometry"]) for feature in features]
                dem_samples = load_dem_samples(
                    client, geometries, args.cache_dir, refresh=args.refresh
                )
            except Exception as exc:
                source_errors["dem"] = str(exc)
                print(f"DEM no disponible: {exc}", file=sys.stderr)
                if args.strict:
                    raise
    finally:
        client.close()

    enriched, stats = enrich_features(
        features,
        source=args.source,
        updated=updated,
        conaf_polygons=conaf_polygons,
        fire_points=fire_points,
        dem_samples=dem_samples,
        workers=max(1, args.workers),
    )

    payload = {
        "type": "FeatureCollection",
        "name": "sigrif_regional_valparaiso_oficial",
        "features": enriched,
        "metadata": {
            "generado": started.isoformat(),
            "capa_base": str(args.input),
            "fuentes": {
                "conaf": CONAF_LAYER_URL,
                "incendios": "https://ide.minagri.gob.cl/descarga-de-capas-shp/desastres/",
                "dem": SRTM_URL,
            },
        },
    }
    _write_json_atomic(args.output, payload, compact=True)

    report = {
        "generado": started.isoformat(),
        "fecha_datos": updated,
        "capa_base": str(args.input),
        "capa_salida": str(args.output),
        "source": args.source,
        "fuentes_ejecutadas": (
            ["conaf", "incendios", "dem"] if args.source == "all" else [args.source]
        ),
        "limit": args.limit,
        "zonas": len(enriched),
        "cobertura": stats,
        "errores_fuentes": source_errors,
        "muestras": _samples(enriched),
        "parametros": {
            "conaf_where": CONAF_WHERE,
            "conaf_max_allowable_offset_deg": CONAF_SIMPLIFY_DEG,
            "conaf_pagina": CONAF_PAGE_SIZE,
            "incendios_temporadas": FIRE_SEASONS,
            "dem_proveedor": DEM_PROVIDER,
            "dem_puntos_max_por_zona": DEM_MAX_POINTS,
            "dem_buffer_deg": DEM_BUFFER_DEG,
        },
        "notas": [
            "vegetation = bosque_nativo + bosque_mixto + plantacion + matorral, "
            "normalizado por la superficie de la zona.",
            "historical_fires cuenta puntos de inicio CONAF, no area quemada.",
            "slope es una pendiente media aproximada por ajuste de plano local, "
            "no un dato oficial de pendiente.",
        ],
    }
    _write_json_atomic(args.report, report)

    print("Resumen:")
    print(f"  zonas: {stats['zonas']}")
    if args.source in {"all", "conaf"}:
        print(
            "  CONAF: "
            f"{stats['conaf_con_cobertura']} con cobertura, "
            f"{stats['conaf_sin_cobertura']} pendientes"
        )
    if args.source in {"all", "fires"}:
        print(
            "  Incendios: "
            f"{stats['incendios_asignados']} eventos asignados, "
            f"{stats['incendios_zonas_sin_eventos']} zonas sin eventos, "
            f"{stats['incendios_pendientes']} pendientes"
        )
    if args.source in {"all", "dem"}:
        print(
            f"  DEM: {stats['dem_con_pendiente']} con pendiente, {stats['dem_fallback']} con prior"
        )
    print(f"  salida: {args.output}")
    print(f"  reporte: {args.report}")
    if source_errors:
        print(f"  errores de fuentes: {source_errors}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
