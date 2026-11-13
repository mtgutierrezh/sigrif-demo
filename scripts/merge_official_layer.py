"""Fusiona la capa censal corregida con los atributos oficiales ya calculados."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "src" / "sigrif" / "data"
BASE = DATA / "cerros_sectores_valparaiso_region.geojson"
OFFICIAL = DATA / "cerros_sectores_valparaiso_region_oficial.geojson"

BASE_KEYS = {
    "Nombre_Cer",
    "name",
    "Comuna",
    "Provincia",
    "Region",
    "Nivel",
    "zone_type",
    "name_source",
    "name_official",
    "GEOCODIGO",
    "URBANO",
    "DISTRITO",
    "ZONA",
    "Población",
    "Fuente_Geometria",
}


def key(feature: dict) -> str:
    props = feature.get("properties") or {}
    geo = props.get("GEOCODIGO")
    return str(geo) if geo else str(props.get("Nombre_Cer") or "")


def main() -> None:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    old = json.loads(OFFICIAL.read_text(encoding="utf-8")) if OFFICIAL.exists() else {"features": []}
    previous = {key(feature): feature for feature in old.get("features", [])}

    result = []
    matched = 0
    pending = 0
    for feature in base["features"]:
        props = dict(feature.get("properties") or {})
        previous_feature = previous.get(key(feature))
        if previous_feature:
            merged = dict(previous_feature.get("properties") or {})
            merged.update({name: props[name] for name in BASE_KEYS if name in props})
            merged["data_quality"] = "oficial"
            matched += 1
        else:
            merged = props
            merged["data_quality"] = "pendiente"
            merged["Estado_Vegetacion"] = "pendiente"
            merged["Estado_Incendios"] = "pendiente"
            merged["Estado_Pendiente"] = "pendiente"
            merged["Fuente_Vegetacion"] = "pendiente"
            merged["Fuente_Incendios"] = "pendiente"
            merged["Fuente_Pendiente"] = "pendiente"
            pending += 1
        result.append({"type": "Feature", "geometry": feature["geometry"], "properties": merged})

    OFFICIAL.write_text(
        json.dumps({"type": "FeatureCollection", "features": result}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"features={len(result)} matched={matched} pending={pending}")


if __name__ == "__main__":
    main()
