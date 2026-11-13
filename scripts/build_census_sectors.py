"""Convierte zonas censales 2017 y construye la capa operativa regional.

Requiere el shapefile nacional del INE (Zonas censales de Chile, 2017).
Uso:
    uv run python scripts/build_census_sectors.py \
        /tmp/opencode/zonas2017/Zonas_censales_Chile_2017.shp
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import shapefile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "sigrif" / "data"
CITY = DATA / "cerros_sectores.geojson"
CENSUS_OUT = DATA / "zonas_censales_valparaiso_2017.geojson"
REGIONAL = DATA / "cerros_sectores_valparaiso_region.geojson"

PRIORS = {
    "PETORCA": (0.45, 8, 28.0),
    "LOS ANDES": (0.35, 5, 30.0),
    "SAN FELIPE": (0.30, 4, 26.0),
    "QUILLOTA": (0.35, 5, 22.0),
    "MARGA MARGA": (0.40, 6, 24.0),
    "VALPARAISO": (0.35, 5, 20.0),
    "SAN ANTONIO": (0.30, 4, 18.0),
    "ISLA DE PASCUA": (0.20, 1, 12.0),
}
ISLAND_OR_CITY = {"VALPARAISO", "ISLA DE PASCUA", "JUAN FERNANDEZ", "VALPARAÍSO", "ISLA DE PASCUA"}


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.upper().split())


def title(value: str) -> str:
    return value.title().replace(" De ", " de ").replace(" Del ", " del ").replace(" La ", " la ")


def geometry(shape) -> dict | None:
    if shape.shapeType == 0:
        return None
    return shape.__geo_interface__


def convert_census(shp: Path) -> int:
    reader = shapefile.Reader(str(shp), encoding="utf-8")
    fields = [field[0] for field in reader.fields[1:]]
    index = {name: position for position, name in enumerate(fields)}
    features: list[dict] = []
    for record, shape in zip(reader.records(), reader.shapes(), strict=True):
        if str(record[index["REGION"]]) != "5":
            continue
        geom = geometry(shape)
        if geom is None:
            continue
        props = {
            "REGION": str(record[index["REGION"]]),
            "NOM_REGION": str(record[index["NOM_REGION"]]),
            "PROVINCIA": str(record[index["PROVINCIA"]]),
            "NOM_PROVINCIA": str(record[index["NOM_PROVIN"]]),
            "COMUNA": str(record[index["COMUNA"]]),
            "NOM_COMUNA": str(record[index["NOM_COMUNA"]]),
            "URBANO": str(record[index["URBANO"]]),
            "DISTRITO": str(record[index["DISTRITO"]]),
            "ZONA": str(record[index["ZONA"]]),
            "GEOCODIGO": str(record[index["GEOCODIGO"]]),
        }
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    payload = {"type": "FeatureCollection", "features": features}
    CENSUS_OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Zonas censales región 05: {len(features)} -> {CENSUS_OUT}")
    return len(features)


def build_regional() -> int:
    city = json.loads(CITY.read_text(encoding="utf-8"))["features"]
    census = json.loads(CENSUS_OUT.read_text(encoding="utf-8"))["features"]
    regional: list[dict] = []
    for feature in city:
        props = dict(feature.get("properties") or {})
        props.update(
            {
                "Comuna": "Valparaíso",
                "Provincia": "Valparaíso",
                "Nivel": "sector",
                "vegetation": 0.35,
                "historical_fires": 5,
                "slope": 20.0,
                "Fuente_Geometria": "SIG Municipalidad de Valparaíso",
            }
        )
        regional.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})

    for feature in census:
        props = feature["properties"]
        comuna = str(props["NOM_COMUNA"])
        if norm(comuna) in ISLAND_OR_CITY:
            continue
        provincia = str(props["NOM_PROVINCIA"])
        vegetation, historical_fires, slope = PRIORS.get(norm(provincia), (0.30, 4, 20.0))
        distrito = str(props["DISTRITO"])
        zona = str(props["ZONA"])
        regional.append(
            {
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": {
                    "Nombre_Cer": f"{title(comuna)} · D{distrito}-Z{zona}",
                    "Comuna": title(comuna),
                    "Provincia": title(provincia),
                    "Nivel": "censal",
                    "Población": 0,
                    "vegetation": vegetation,
                    "historical_fires": historical_fires,
                    "slope": slope,
                    "GEOCODIGO": str(props["GEOCODIGO"]),
                    "Fuente_Geometria": "Censo 2017 INE",
                },
            }
        )
    payload = {"type": "FeatureCollection", "features": regional}
    REGIONAL.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Zonas operativas: {len(regional)} -> {REGIONAL}")
    return len(regional)


if __name__ == "__main__":
    import sys

    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/tmp/opencode/zonas2017/Zonas_censales_Chile_2017.shp"
    )
    convert_census(source)
    build_regional()
