import json
from pathlib import Path
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select

from ..db import SessionLocal, init_db
from ..models import Reading, RiskCell, Zone

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ZONES_FILE = DATA_DIR / "cerros_sectores.geojson"
CELLS_FILE = DATA_DIR / "risk_cells.geojson"
COMUNA = "Valparaíso"


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


def load_zones(path: Path = ZONES_FILE) -> list[tuple[str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    zones = []
    for feature in data["features"]:
        name = feature["properties"]["Nombre_Cer"].strip()
        zones.append((name, COMUNA, _multipolygon_wkt(feature["geometry"])))
    return zones


def load_cells(path: Path = CELLS_FILE) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["features"]


def seed_zones() -> None:
    zones = load_zones()
    with SessionLocal() as session:
        count = session.scalar(select(func.count(Zone.id))) or 0
        if count == len(zones):
            print("Las zonas ya existen")
            return
        if count:
            session.execute(delete(Reading))
            session.execute(delete(Zone))
            session.commit()
        for name, comuna, wkt in zones:
            session.add(
                Zone(
                    name=name,
                    comuna=comuna,
                    geometry=WKTElement(wkt, srid=4326),
                    risk_level="Bajo",
                    risk_score=0.0,
                )
            )
        session.commit()
    print(f"Zonas cargadas: {len(zones)}")


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
