from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from ..db import SessionLocal, init_db
from ..models import Zone


def _polygon(west: float, south: float, east: float, north: float) -> str:
    return (
        f"MULTIPOLYGON((({west} {south}, {east} {south}, {east} {north}, "
        f"{west} {north}, {west} {south})))"
    )


ZONES = [
    ("Valparaiso", "Valparaiso", _polygon(-71.68, -33.06, -71.60, -33.01)),
    ("Vina del Mar", "Vina del Mar", _polygon(-71.58, -33.04, -71.50, -32.98)),
    ("Quilpue", "Quilpue", _polygon(-71.50, -33.08, -71.42, -33.02)),
    ("Villa Alemana", "Villa Alemana", _polygon(-71.40, -33.06, -71.32, -33.00)),
    ("Concon", "Concon", _polygon(-71.56, -32.95, -71.50, -32.90)),
    ("Casablanca", "Casablanca", _polygon(-71.45, -33.35, -71.35, -33.25)),
]


def seed() -> None:
    init_db()
    with SessionLocal() as session:
        existing = session.scalar(select(Zone.id).limit(1))
        if existing is not None:
            print("Las zonas ya existen")
            return
        for name, comuna, wkt in ZONES:
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
    print(f"Zonas cargadas: {len(ZONES)}")


if __name__ == "__main__":
    seed()
