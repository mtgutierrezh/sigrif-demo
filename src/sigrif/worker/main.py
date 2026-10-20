import json
from pathlib import Path
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select

from ..db import SessionLocal, init_db
from ..models import Reading, Zone

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cerros_sectores.geojson"
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


def load_zones(path: Path = DATA_FILE) -> list[tuple[str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    zones = []
    for feature in data["features"]:
        name = feature["properties"]["Nombre_Cer"].strip()
        zones.append((name, COMUNA, _multipolygon_wkt(feature["geometry"])))
    return zones


def seed() -> None:
    init_db()
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


if __name__ == "__main__":
    seed()
