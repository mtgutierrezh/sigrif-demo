"""Construcción de la malla H3 res 8 para la Región de Valparaíso continental.

La malla usa los polígonos comunales DPA 2022 como máscara terrestre. Las
fracciones de combustible se calculan desde el catastro CONAF 2019 cuando el
archivo está disponible y, si no, se heredan de la zona oficial más cercana.
La atribución a zonas usa intersección de área y, para celdas rurales, la zona
más cercana de la misma comuna. Las islas (Isla de Pascua y Juan Fernández) se
excluyen porque la capa solicitada es continental.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import h3
from shapely import STRtree
from shapely.geometry import Polygon, shape
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "src" / "sigrif" / "data"
DEFAULT_ZONES = DATA_DIR / "cerros_sectores_valparaiso_region_oficial.geojson"
DEFAULT_COMUNAS = DATA_DIR / "dpa_valparaiso_2022.geojson"
DEFAULT_CONAF = ROOT / "ml" / "cache" / "conaf" / "valparaiso_uso_suelo.geojson"
DEFAULT_FIRES = ROOT / "ml" / "cache" / "fires" / "incendios_valparaiso_2010_2025.geojson"
REGIONAL_OUTPUT = DATA_DIR / "h3_valparaiso_region_res8.geojson"
ZONES_OUTPUT = DATA_DIR / "h3_valparaiso_zonas_res8.geojson"

ISLAND_COMUNAS = {"Isla de Pascua", "Juan Fernández"}
FUEL_FIELDS = ("native", "plantation", "shrub", "grass", "agriculture", "urban")
FUEL_LABELS = {
    "native": "Bosque nativo",
    "plantation": "Plantación",
    "shrub": "Matorral",
    "grass": "Pradera",
    "agriculture": "Agrícola",
    "urban": "Urbano",
}
DEFAULT_MIN_CELL_FRACTION = 0.02


def load_features(path: Path | str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(data["features"])


def is_continental(feature: dict[str, Any]) -> bool:
    properties = feature.get("properties") or {}
    comuna = str(properties.get("Comuna") or properties.get("comuna") or "").strip()
    return comuna not in ISLAND_COMUNAS


def cell_polygon(index: str) -> Polygon:
    boundary = h3.cell_to_boundary(index)
    return orient(Polygon([(lng, lat) for lat, lng in boundary]), sign=1.0)


def _largest_polygon(geometry: Any) -> Polygon | None:
    if geometry is None or geometry.is_empty:
        return None
    if geometry.geom_type == "Polygon":
        return geometry
    if geometry.geom_type == "MultiPolygon":
        return max(geometry.geoms, key=lambda item: item.area)
    return None


def _clip_cell(
    cell: Polygon,
    boundary: Any,
    min_fraction: float = DEFAULT_MIN_CELL_FRACTION,
) -> Polygon | None:
    try:
        clipped = cell.intersection(boundary)
    except Exception:
        return None
    polygon = _largest_polygon(clipped)
    if polygon is None or polygon.is_empty:
        return None
    if polygon.area < cell.area * min_fraction:
        return None
    return orient(polygon, sign=1.0)


def _round_ring(ring: Any, precision: int) -> list[list[float]]:
    return [[round(float(x), precision), round(float(y), precision)] for x, y in ring.coords]


def geometry_dict(polygon: Polygon, precision: int = 6) -> dict[str, Any]:
    rings = [_round_ring(polygon.exterior, precision)]
    rings.extend(_round_ring(interior, precision) for interior in polygon.interiors)
    return {"type": "Polygon", "coordinates": rings}


def _polyfill(geometry: Any, resolution: int) -> set[str]:
    return set(h3.geo_to_cells(geometry.__geo_interface__, resolution))


def _safe_shape(geometry: dict[str, Any]) -> Any | None:
    try:
        return shape(geometry)
    except Exception:
        return None


def _safe_intersection(left: Any, right: Any) -> Any | None:
    try:
        return left.intersection(right)
    except Exception:
        return None


def _safe_area(left: Any, right: Any) -> float | None:
    result = _safe_intersection(left, right)
    if result is None:
        return None
    return float(result.area)


def _fuel_class(uso: str | None, subuso: str | None) -> str | None:
    uso = (uso or "").strip()
    subuso = (subuso or "").strip()
    if uso == "Bosques":
        return "plantation" if subuso == "Plantación" else "native"
    if uso == "Praderas y Matorrales":
        return "grass" if subuso in {"Praderas", "Matorral-Pradera"} else "shrub"
    if uso == "Terrenos Agrícolas":
        return "agriculture"
    if uso == "Áreas Urbanas e Industriales":
        return "urban"
    return None


class FuelIndex:
    def __init__(self, path: Path | str):
        geometries: list[Any] = []
        classes: list[str] = []
        for feature in load_features(path):
            properties = feature.get("properties") or {}
            fuel_class = _fuel_class(properties.get("USO"), properties.get("SUBUSO"))
            if fuel_class is None:
                continue
            geometry = _safe_shape(feature["geometry"])
            if geometry is None:
                continue
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
            if geometry.is_empty:
                continue
            geometries.append(geometry)
            classes.append(fuel_class)
        self.geometries = geometries
        self.classes = classes
        self.tree = STRtree(geometries)

    def fractions(self, cell: Polygon) -> dict[str, float]:
        areas: dict[str, float] = defaultdict(float)
        for position in self.tree.query(cell):
            intersection = _safe_intersection(cell, self.geometries[int(position)])
            if intersection is None or intersection.is_empty:
                continue
            areas[self.classes[int(position)]] += intersection.area
        if not cell.area:
            return {field: 0.0 for field in FUEL_FIELDS}
        fractions = {
            field: min(1.0, max(0.0, areas.get(field, 0.0) / cell.area)) for field in FUEL_FIELDS
        }
        total = sum(fractions.values())
        if total > 1.0:
            fractions = {field: value / total for field, value in fractions.items()}
        return {field: round(value, 4) for field, value in fractions.items()}


class FireIndex:
    def __init__(self, path: Path | str):
        points = []
        for feature in load_features(path):
            if (feature.get("geometry") or {}).get("type") != "Point":
                continue
            point = _safe_shape(feature["geometry"])
            if point is not None:
                points.append(point)
        self.tree = STRtree(points)

    def count(self, cell: Polygon) -> int:
        if not len(self.tree):
            return 0
        return int(len(self.tree.query(cell, predicate="within")))


class ZoneIndex:
    def __init__(self, zones: list[dict[str, Any]]):
        self.zones = zones
        self.geometries = [shape(feature["geometry"]) for feature in zones]
        self.tree = STRtree(self.geometries)
        self.positions = {id(feature): position for position, feature in enumerate(zones)}
        self.by_comuna: dict[str, list[int]] = defaultdict(list)
        for position, feature in enumerate(zones):
            properties = feature.get("properties") or {}
            comuna = str(properties.get("Comuna") or properties.get("comuna") or "").strip()
            self.by_comuna[comuna].append(position)
        self.comuna_trees: dict[str, STRtree] = {}

    def _comuna_tree(self, comuna: str) -> tuple[STRtree | None, list[int]]:
        positions = self.by_comuna.get(comuna, [])
        if not positions:
            return None, []
        if comuna not in self.comuna_trees:
            self.comuna_trees[comuna] = STRtree([self.geometries[i] for i in positions])
        return self.comuna_trees[comuna], positions

    def match(
        self,
        cell: Polygon,
        comuna: str,
        fallback: bool = True,
    ) -> tuple[dict[str, Any] | None, str | None, float | None]:
        best_position: int | None = None
        best_area = 0.0
        for position in self.tree.query(cell):
            area = _safe_area(cell, self.geometries[int(position)])
            if area is None:
                continue
            if area > best_area:
                best_area = area
                best_position = int(position)
        if best_position is not None:
            return self.zones[best_position], "intersect", 0.0
        if not fallback or not len(self.tree):
            return None, None, None
        tree, positions = self._comuna_tree(comuna)
        if tree is not None:
            nearest = int(tree.nearest(cell))
            position = positions[nearest]
        else:
            position = int(self.tree.nearest(cell))
        distance = cell.distance(self.geometries[position])
        return self.zones[position], "nearest", distance

    def geometry_for(self, feature: dict[str, Any]) -> Any:
        return self.geometries[self.positions[id(feature)]]


def _haversine_m(first: Any, second: Any) -> float:
    lon1, lat1 = float(first[0]), float(first[1])
    lon2, lat2 = float(second[0]), float(second[1])
    radius = 6_371_008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(value))


def _zone_distance_m(cell: Polygon, zone_geometry: Any) -> float:
    first, second = nearest_points(cell, zone_geometry)
    return round(_haversine_m(first.coords[0], second.coords[0]), 1)


def _screening_score(fractions: dict[str, float], slope: float, fires: int) -> tuple[str, float]:
    wildland = sum(
        fractions[field] for field in ("native", "plantation", "shrub", "grass", "agriculture")
    )
    score = 0.08 + 0.5 * wildland + 0.004 * max(0.0, slope) + 0.01 * min(15, max(0, fires))
    score = round(min(0.95, max(0.0, score)), 3)
    level = "Alto" if score >= 0.7 else "Medio" if score >= 0.4 else "Bajo"
    return level, score


def _zone_fuel(properties: dict[str, Any]) -> dict[str, float]:
    return {
        field: min(1.0, max(0.0, float(properties.get(f"fuel_{field}", 0.0) or 0.0)))
        for field in FUEL_FIELDS
    }


def _dominant(fractions: dict[str, float]) -> str:
    field, value = max(fractions.items(), key=lambda item: item[1])
    return FUEL_LABELS[field] if value > 0 else "Sin dato"


def _source_label(path: Path | str | None) -> str | None:
    if path is None:
        return None
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _candidate_cells(
    comunas: list[dict[str, Any]],
    resolution: int,
    min_fraction: float,
) -> tuple[dict[str, dict[str, Any]], int]:
    candidates: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for feature in comunas:
        properties = feature.get("properties") or {}
        comuna = str(properties.get("comuna") or properties.get("Comuna") or "").strip()
        provincia = str(properties.get("provincia") or properties.get("Provincia") or "").strip()
        boundary = shape(feature["geometry"])
        for index in sorted(_polyfill(boundary, resolution)):
            cell = cell_polygon(index)
            clipped = _clip_cell(cell, boundary, min_fraction)
            if clipped is None:
                continue
            record = {
                "geometry": clipped,
                "comuna": comuna,
                "provincia": provincia,
                "fixed_zone": None,
            }
            previous = candidates.get(index)
            if previous is not None:
                duplicates += 1
                if clipped.area <= previous["geometry"].area:
                    continue
            candidates[index] = record
    return candidates, duplicates


def _candidate_cells_from_zones(
    zones: list[dict[str, Any]],
    resolution: int,
    min_fraction: float,
) -> tuple[dict[str, dict[str, Any]], int]:
    candidates: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for feature in zones:
        properties = feature.get("properties") or {}
        comuna = str(properties.get("Comuna") or properties.get("comuna") or "").strip()
        provincia = str(properties.get("Provincia") or properties.get("provincia") or "").strip()
        boundary = shape(feature["geometry"])
        for index in sorted(_polyfill(boundary, resolution)):
            cell = cell_polygon(index)
            clipped = _clip_cell(cell, boundary, min_fraction)
            if clipped is None:
                continue
            record = {
                "geometry": clipped,
                "comuna": comuna,
                "provincia": provincia,
                "fixed_zone": feature,
            }
            previous = candidates.get(index)
            if previous is not None:
                duplicates += 1
                if clipped.area <= previous["geometry"].area:
                    continue
            candidates[index] = record
    return candidates, duplicates


def build_mesh(
    *,
    zones_path: Path | str = DEFAULT_ZONES,
    comunas_path: Path | str = DEFAULT_COMUNAS,
    conaf_path: Path | str | None = DEFAULT_CONAF,
    fires_path: Path | str | None = DEFAULT_FIRES,
    resolution: int = 8,
    scope: str = "region",
    zone_fallback: bool = True,
    min_fraction: float = DEFAULT_MIN_CELL_FRACTION,
    precision: int = 6,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if resolution < 4 or resolution > 12:
        raise ValueError("La resolución H3 debe estar entre 4 y 12")
    if scope not in {"region", "zones"}:
        raise ValueError("El alcance debe ser 'region' o 'zones'")

    all_zones = load_features(zones_path)
    continental_zones = [feature for feature in all_zones if is_continental(feature)]
    island_zones = len(all_zones) - len(continental_zones)

    if scope == "region":
        comunas = [
            feature
            for feature in load_features(comunas_path)
            if str((feature.get("properties") or {}).get("comuna") or "").strip()
            not in ISLAND_COMUNAS
        ]
        candidates, duplicates = _candidate_cells(comunas, resolution, min_fraction)
    else:
        comunas = []
        candidates, duplicates = _candidate_cells_from_zones(
            continental_zones, resolution, min_fraction
        )

    fuel_source = None
    fuel_index = None
    if conaf_path is not None and Path(conaf_path).exists():
        fuel_index = FuelIndex(conaf_path)
        fuel_source = _source_label(conaf_path)

    fires_source = None
    fire_index = None
    if fires_path is not None and Path(fires_path).exists():
        fire_index = FireIndex(fires_path)
        fires_source = _source_label(fires_path)

    zone_index = ZoneIndex(continental_zones)
    generated_at = datetime.now(UTC).isoformat()
    features: list[dict[str, Any]] = []
    in_zone = 0
    nearest_zone = 0
    without_zone = 0
    covered_zone_ids: set[int] = set()
    by_comuna: Counter[str] = Counter()

    for index in sorted(candidates):
        record = candidates[index]
        cell = record["geometry"]
        comuna = record["comuna"]
        provincia = record["provincia"]
        fixed_zone = record["fixed_zone"]
        zone_feature: dict[str, Any] | None
        zone_match: str | None
        zone_distance: float | None
        if fixed_zone is not None:
            zone_feature = fixed_zone
            zone_match = "intersect"
            zone_distance = 0.0
        else:
            zone_feature, zone_match, zone_distance = zone_index.match(
                cell, comuna, fallback=zone_fallback
            )

        zone_properties = (zone_feature or {}).get("properties") or {}
        zone_name = str(
            zone_properties.get("name")
            or zone_properties.get("Nombre_Cer")
            or f"Área rural de {comuna}"
        ).strip()
        zone_id = zone_index.positions[id(zone_feature)] + 1 if zone_feature is not None else None
        if zone_id is not None:
            covered_zone_ids.add(zone_id)
        if zone_match == "intersect":
            in_zone += 1
        elif zone_match == "nearest":
            nearest_zone += 1
        else:
            without_zone += 1

        if fuel_index is not None:
            fractions = fuel_index.fractions(cell)
            if not any(fractions.values()):
                fractions = _zone_fuel(zone_properties)
        else:
            fractions = _zone_fuel(zone_properties)

        slope = float(zone_properties.get("slope", 15.0) or 0.0)
        zone_fires = int(zone_properties.get("historical_fires", 0) or 0)
        if zone_match == "intersect" or fire_index is None:
            fires = zone_fires
        else:
            fires = fire_index.count(cell)

        raw_score = zone_properties.get("risk_score")
        raw_level = zone_properties.get("risk_level")
        if raw_score is None:
            risk_level, risk_score = _screening_score(fractions, slope, fires)
        else:
            risk_score = round(float(raw_score), 3)
            risk_level = str(raw_level or "") or (
                "Alto" if risk_score >= 0.7 else "Medio" if risk_score >= 0.4 else "Bajo"
            )

        properties = {
            "h3": index,
            "zone_id": zone_id,
            "comuna": comuna,
            "provincia": provincia,
            "zone_name": zone_name,
            "zone_match": zone_match,
            "dominant_fuel": _dominant(fractions),
            "fuel_native": fractions["native"],
            "fuel_plantation": fractions["plantation"],
            "fuel_shrub": fractions["shrub"],
            "fuel_grass": fractions["grass"],
            "fuel_agriculture": fractions["agriculture"],
            "fuel_urban": fractions["urban"],
            "slope": round(slope, 2),
            "historical_fires": fires,
            "wui_distance_m": 0.0,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "updated_at": generated_at,
        }
        if zone_distance is not None and zone_match == "nearest" and zone_feature is not None:
            properties["zone_distance_m"] = _zone_distance_m(
                cell, zone_index.geometry_for(zone_feature)
            )
        features.append(
            {
                "type": "Feature",
                "geometry": geometry_dict(cell, precision),
                "properties": properties,
            }
        )
        by_comuna[comuna] += 1

    urban_cells = [
        (position, cell_polygon(feature["properties"]["h3"]))
        for position, feature in enumerate(features)
        if feature["properties"]["dominant_fuel"] == FUEL_LABELS["urban"]
    ]
    if urban_cells:
        urban_tree = STRtree([cell for _, cell in urban_cells])
        for feature in features:
            if feature["properties"]["dominant_fuel"] == FUEL_LABELS["urban"]:
                continue
            cell = cell_polygon(feature["properties"]["h3"])
            nearest = int(urban_tree.nearest(cell))
            urban_geometry = urban_cells[nearest][1]
            first, second = nearest_points(cell, urban_geometry)
            feature["properties"]["wui_distance_m"] = round(
                _haversine_m(first.coords[0], second.coords[0]), 1
            )

    zones_continental = len(continental_zones)
    mesh_tree = STRtree([record["geometry"] for record in candidates.values()])
    geometrically_covered = 0
    for zone in continental_zones:
        zone_geometry = shape(zone["geometry"])
        if len(mesh_tree.query(zone_geometry, predicate="intersects")):
            geometrically_covered += 1
    metadata = {
        "name": "sigrif_h3_valparaiso_region_res8"
        if scope == "region"
        else "sigrif_h3_valparaiso_zonas_res8",
        "scope": "region_continental" if scope == "region" else "zonas_oficiales",
        "resolution": resolution,
        "generated_at": generated_at,
        "cells_total": len(features),
        "cells_in_zone": in_zone,
        "cells_by_nearest_zone": nearest_zone,
        "cells_without_zone": without_zone,
        "duplicates_dropped": duplicates,
        "zones_total": len(all_zones),
        "zones_continental": zones_continental,
        "island_zones_excluded": island_zones,
        "zones_covered": geometrically_covered,
        "zones_assigned": len(covered_zone_ids),
        "zones_coverage_pct": round(100 * geometrically_covered / zones_continental, 2)
        if zones_continental
        else 0.0,
        "zones_assigned_pct": round(100 * len(covered_zone_ids) / zones_continental, 2)
        if zones_continental
        else 0.0,
        "comunas_with_cells": len(by_comuna),
        "cells_by_comuna": dict(sorted(by_comuna.items())),
        "source_zones": _source_label(zones_path),
        "source_comunas": _source_label(comunas_path) if scope == "region" else None,
        "source_fuel": fuel_source,
        "source_fires": fires_source,
        "zone_id_note": (
            "zone_id es el ordinal de la zona oficial en el GeoJSON; el worker "
            "lo remapea al id de la tabla zones usando zone_name."
        ),
        "fuel_method": "conaf_intersection" if fuel_index is not None else "zone_inheritance",
        "fires_method": "zone" if fire_index is None else "zone_intersection_point_count",
        "risk_note": (
            "risk_level y risk_score se heredan de la zona cuando existen; en caso "
            "contrario se usa un cribado estático de combustible, pendiente e "
            "incendios históricos que no reemplaza al modelo."
        ),
    }
    return features, metadata


def build_payload(
    features: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "name": metadata["name"],
        "metadata": metadata,
        "features": features,
    }


def write_payload(path: Path | str, payload: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return destination
