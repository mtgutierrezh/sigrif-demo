from __future__ import annotations

import csv
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "sigrif" / "data"
CITY = DATA / "cerros_sectores.geojson"
CENSUS = DATA / "zonas_censales_valparaiso_2017.geojson"
DPA = DATA / "dpa_valparaiso_2022.geojson"
NAMES = DATA / "census_names.json"
OUTPUT = DATA / "cerros_sectores_valparaiso_region.geojson"
COVERAGE = ROOT / "ml" / "zone_coverage.csv"

PRIORS: dict[str, tuple[float, int, float]] = {
    "Petorca": (0.45, 8, 28.0),
    "Los Andes": (0.35, 5, 30.0),
    "San Felipe de Aconcagua": (0.30, 4, 26.0),
    "Quillota": (0.35, 5, 22.0),
    "Marga Marga": (0.40, 6, 24.0),
    "Valparaíso": (0.35, 5, 20.0),
    "San Antonio": (0.30, 4, 18.0),
    "Isla de Pascua": (0.20, 1, 12.0),
}


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in text if not unicodedata.combining(char)).upper().strip()


def geokey(value: Any) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    city = read_json(CITY)["features"]
    census = read_json(CENSUS)["features"]
    dpa = read_json(DPA)["features"]
    names = read_json(NAMES)
    dpa_by_name = {normalize(str(feature["properties"]["comuna"])): feature for feature in dpa}
    name_by_geo = {geokey(key): value for key, value in names.items()}
    used: set[str] = set()
    counts: Counter[str] = Counter()
    official_counts: Counter[str] = Counter()
    referential_counts: Counter[str] = Counter()
    output: list[dict[str, Any]] = []

    def unique_name(base: str, comuna: str, suffix: str) -> str:
        candidate = base.strip() or f"Zona censal {suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        candidate = f"{base} · {comuna}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        candidate = f"{base} · {suffix}"
        used.add(candidate)
        return candidate

    for feature in city:
        props = dict(feature.get("properties") or {})
        name = str(props.get("Nombre_Cer") or "").strip()
        if not name:
            continue
        props.update(
            {
                "Nombre_Cer": name,
                "name": name,
                "Comuna": "Valparaíso",
                "Provincia": "Valparaíso",
                "Region": "Valparaíso",
                "Nivel": "sector_municipal",
                "zone_type": "sector_municipal",
                "name_source": "SIG Municipalidad de Valparaíso",
                "name_official": True,
                "Fuente_Geometria": "SIG Municipalidad de Valparaíso",
            }
        )
        output.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})
        counts["Valparaíso"] += 1
        official_counts["Valparaíso"] += 1

    for feature in census:
        props = dict(feature.get("properties") or {})
        raw_comuna = str(props.get("NOM_COMUNA") or "")
        lookup = dpa_by_name.get(normalize(raw_comuna))
        if lookup is None:
            continue
        comuna = str(lookup["properties"]["comuna"])
        if comuna == "Valparaíso":
            continue
        provincia = str(lookup["properties"].get("provincia") or props.get("NOM_PROVINCIA") or "")
        geo = geokey(props.get("GEOCODIGO"))
        found = name_by_geo.get(geo, {})
        if str(found.get("field")) == "osm_landuse" and found.get("osm_value") != "residential":
            found = {}
        base = str(found.get("name") or "").strip()
        if any(token in base.lower() for token in ("industrial", "conservera", "s.a.", "planta")):
            base = ""
        source = "OpenStreetMap/Photon" if base else "Censo 2017 INE (localidad)"
        official = False
        if not base:
            locality = str(props.get("URBANO") or "").strip()
            base = locality.title() if locality else f"Zona censal {geo}"
        suffix = f"D{int(float(props.get('DISTRITO') or 0))}-Z{int(float(props.get('ZONA') or 0))}"
        name = unique_name(base, comuna, suffix)
        vegetation, fires, slope = PRIORS.get(provincia, (0.30, 4.0, 18.0))
        props.update(
            {
                "Nombre_Cer": name,
                "name": name,
                "Comuna": comuna,
                "Provincia": provincia,
                "Region": "Valparaíso",
                "Nivel": "zona_censal",
                "zone_type": "zona_censal",
                "name_source": source,
                "name_official": official,
                "Población": 0,
                "vegetation": vegetation,
                "historical_fires": fires,
                "slope": slope,
                "GEOCODIGO": geo,
                "URBANO": props.get("URBANO"),
                "DISTRITO": props.get("DISTRITO"),
                "ZONA": props.get("ZONA"),
                "Fuente_Geometria": "Censo 2017 INE",
            }
        )
        output.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})
        counts[comuna] += 1
        if official:
            official_counts[comuna] += 1
        else:
            referential_counts[comuna] += 1

    juan = dpa_by_name.get(normalize("Juan Fernández"))
    if juan is not None:
        props = {
            "Nombre_Cer": "Juan Fernández",
            "name": "Juan Fernández",
            "Comuna": "Juan Fernández",
            "Provincia": str(juan["properties"].get("provincia") or "Valparaíso"),
            "Region": "Valparaíso",
            "Nivel": "comuna",
            "zone_type": "comuna",
            "name_source": "DPA 2022 IDE Minagri/MINVU",
            "name_official": True,
            "Superficie_km2": juan["properties"].get("superficie"),
            "vegetation": 0.20,
            "historical_fires": 1,
            "slope": 12.0,
            "Fuente_Geometria": "DPA 2022, IDE Minagri/MINVU",
        }
        output.append({"type": "Feature", "geometry": juan["geometry"], "properties": props})
        counts["Juan Fernández"] += 1
        official_counts["Juan Fernández"] += 1

    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": output}, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = []
    for feature in dpa:
        dpa_props = feature["properties"]
        comuna = str(dpa_props["comuna"])
        rows.append(
            {
                "comuna": comuna,
                "provincia": str(dpa_props.get("provincia") or ""),
                "zonas": counts.get(comuna, 0),
                "sectores_municipales": sum(
                    1
                    for item in output
                    if item["properties"].get("Comuna") == comuna
                    and item["properties"].get("zone_type") == "sector_municipal"
                ),
                "zonas_censales": sum(
                    1
                    for item in output
                    if item["properties"].get("Comuna") == comuna
                    and item["properties"].get("zone_type") == "zona_censal"
                ),
                "comuna_poligono": sum(
                    1
                    for item in output
                    if item["properties"].get("Comuna") == comuna
                    and item["properties"].get("zone_type") == "comuna"
                ),
                "nombre_oficial": official_counts.get(comuna, 0),
                "nombre_referencial": referential_counts.get(comuna, 0),
            }
        )
    COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    with COVERAGE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Zonas: {len(output)}; comunas: {len(rows)}")
    print(f"Faltantes: {[row['comuna'] for row in rows if row['zonas'] == 0]}")
    print(f"Cobertura: {COVERAGE}")


if __name__ == "__main__":
    main()
