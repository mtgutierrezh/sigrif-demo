import json
from pathlib import Path
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select

from ..db import SessionLocal, init_db
from ..models import Reading, RiskCell, Zone

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ZONES_BASE_FILE = DATA_DIR / "cerros_sectores_valparaiso_region.geojson"
ZONES_OFFICIAL_FILE = DATA_DIR / "cerros_sectores_valparaiso_region_oficial.geojson"


ZONES_FILE = ZONES_OFFICIAL_FILE if ZONES_OFFICIAL_FILE.exists() else ZONES_BASE_FILE
CELLS_FILE = DATA_DIR / "risk_cells.geojson"


def _multipolygon_wkt(geometry: dict[str, Any]) -> str:
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise ValueError(f"Geometría no soportada: {geometry['type']}")

    polygons_wkt = []
    for polygon in polygons:
        rings = []
        for ring in polygon:
            coordinates = ", ".join(f"{point[0]} {point[1]}" for point in ring)
            rings.append(f"({coordinates})")
        polygons_wkt.append("(" + ", ".join(rings) + ")")
    return "MULTIPOLYGON(" + ", ".join(polygons_wkt) + ")"


def _polygon_wkt(geometry: dict[str, Any]) -> str:
    rings = []
    for ring in geometry["coordinates"]:
        coordinates = ", ".join(f"{point[0]} {point[1]}" for point in ring)
        rings.append(f"({coordinates})")
    return "POLYGON(" + ", ".join(rings) + ")"


def load_zones(path: Path = ZONES_FILE) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    zones: list[dict[str, Any]] = []
    for feature in data["features"]:
        properties = feature.get("properties") or {}
        name = str(properties.get("Nombre_Cer") or properties.get("comuna") or "").strip()
        comuna = str(properties.get("Comuna") or properties.get("comuna") or "").strip()
        if not name or not comuna:
            continue
        zones.append(
            {
                "name": name,
                "comuna": comuna,
                "provincia": str(properties.get("Provincia") or "").strip(),
                "region": str(properties.get("Region") or "Valparaíso").strip(),
                "zone_type": str(
                    properties.get("zone_type") or properties.get("Nivel") or "comunal"
                ),
                "name_source": str(properties.get("name_source") or "desconocida"),
                "name_official": bool(properties.get("name_official", False)),
                "level": str(properties.get("Nivel") or "comunal"),
                "vegetation": float(properties.get("vegetation", 0.3)),
                "historical_fires": int(properties.get("historical_fires", 0)),
                "slope": float(properties.get("slope", 15.0)),
                "fuel_native": float(properties.get("fuel_native", 0.0)),
                "fuel_plantation": float(properties.get("fuel_plantation", 0.0)),
                "fuel_shrub": float(properties.get("fuel_shrub", 0.0)),
                "fuel_grass": float(properties.get("fuel_grass", 0.0)),
                "fuel_agriculture": float(properties.get("fuel_agriculture", 0.0)),
                "fuel_urban": float(properties.get("fuel_urban", 0.0)),
                "dominant_fuel": str(properties.get("dominant_fuel") or "Sin dato"),
                "wkt": _multipolygon_wkt(feature["geometry"]),
            }
        )
    return zones


def seed_zones() -> None:
    zones = load_zones()
    with SessionLocal() as session:
        count = session.scalar(select(func.count(Zone.id))) or 0
        if count == len(zones):
            existing = {zone.name: zone for zone in session.scalars(select(Zone)).all()}
            updated = 0
            for zone_data in zones:
                current = existing.get(zone_data["name"])
                if current is None:
                    continue
                current.name = zone_data["name"]
                current.comuna = zone_data["comuna"]
                current.provincia = zone_data["provincia"]
                current.region = zone_data["region"]
                current.zone_type = zone_data["zone_type"]
                current.name_source = zone_data["name_source"]
                current.name_official = zone_data["name_official"]
                current.vegetation = zone_data["vegetation"]
                current.historical_fires = zone_data["historical_fires"]
                current.slope = zone_data["slope"]
                current.fuel_native = zone_data["fuel_native"]
                current.fuel_plantation = zone_data["fuel_plantation"]
                current.fuel_shrub = zone_data["fuel_shrub"]
                current.fuel_grass = zone_data["fuel_grass"]
                current.fuel_agriculture = zone_data["fuel_agriculture"]
                current.fuel_urban = zone_data["fuel_urban"]
                current.dominant_fuel = zone_data["dominant_fuel"]
                updated += 1
            session.commit()
            print(f"Zonas actualizadas: {updated}")
            return
        if count:
            session.execute(delete(Reading))
            session.execute(delete(Zone))
            session.commit()
        for zone_data in zones:
            session.add(
                Zone(
                    name=zone_data["name"],
                    comuna=zone_data["comuna"],
                    provincia=zone_data["provincia"],
                    region=zone_data["region"],
                    zone_type=zone_data["zone_type"],
                    name_source=zone_data["name_source"],
                    name_official=zone_data["name_official"],
                    geometry=WKTElement(zone_data["wkt"], srid=4326),
                    risk_level="Bajo",
                    risk_score=0.0,
                    vegetation=zone_data["vegetation"],
                    historical_fires=zone_data["historical_fires"],
                    slope=zone_data["slope"],
                    fuel_native=zone_data["fuel_native"],
                    fuel_plantation=zone_data["fuel_plantation"],
                    fuel_shrub=zone_data["fuel_shrub"],
                    fuel_grass=zone_data["fuel_grass"],
                    fuel_agriculture=zone_data["fuel_agriculture"],
                    fuel_urban=zone_data["fuel_urban"],
                    dominant_fuel=zone_data["dominant_fuel"],
                )
            )
        session.commit()
        print(f"Zonas cargadas: {len(zones)}")


def load_cells(path: Path = CELLS_FILE) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["features"])


def seed_cells() -> None:
    features = load_cells()
    with SessionLocal() as session:
        count = session.scalar(select(func.count(RiskCell.h3))) or 0
        if count == len(features):
            print("Las celdas ya existen")
            return
        if count:
            session.execute(delete(RiskCell))
            session.commit()
        for feature in features:
            properties = feature["properties"]
            session.add(
                RiskCell(
                    h3=properties["h3"],
                    geometry=WKTElement(_polygon_wkt(feature["geometry"]), srid=4326),
                    dominant_fuel=properties["dominant_fuel"],
                    fuel_native=properties["fuel_native"],
                    fuel_plantation=properties["fuel_plantation"],
                    fuel_shrub=properties["fuel_shrub"],
                    fuel_grass=properties["fuel_grass"],
                    fuel_agriculture=properties["fuel_agriculture"],
                    fuel_urban=properties["fuel_urban"],
                    wui_distance_m=properties["wui_distance_m"],
                    risk_level=properties["risk_level"],
                    risk_score=properties["risk_score"],
                )
            )
        session.commit()
    print(f"Celdas cargadas: {len(features)}")


def seed() -> None:
    init_db()
    seed_zones()
    seed_cells()


if __name__ == "__main__":
    seed()
