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
        native = float(merged.get("veg_bosque_nativo_frac") or 0) + float(
            merged.get("veg_bosque_mixto_frac") or 0
        )
        plantation = float(merged.get("veg_plantacion_frac") or 0)
        shrub = float(merged.get("veg_matorral_frac") or 0)
        grass = float(merged.get("veg_pradera_frac") or 0)
        agriculture = float(merged.get("veg_agricola_frac") or 0)
        urban = float(merged.get("veg_urbano_frac") or 0)
        merged.update(
            {
                "fuel_native": round(native, 6),
                "fuel_plantation": round(plantation, 6),
                "fuel_shrub": round(shrub, 6),
                "fuel_grass": round(grass, 6),
                "fuel_agriculture": round(agriculture, 6),
                "fuel_urban": round(urban, 6),
            }
        )
        fuels = {
            "Bosque nativo": native,
            "Plantación": plantation,
            "Matorral": shrub,
            "Pradera": grass,
            "Agrícola": agriculture,
            "Urbano": urban,
        }
        dominant = max(fuels, key=fuels.get)
        merged["dominant_fuel"] = dominant if fuels[dominant] > 0 else "Sin dato"
        result.append({"type": "Feature", "geometry": feature["geometry"], "properties": merged})

    OFFICIAL.write_text(
        json.dumps({"type": "FeatureCollection", "features": result}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"features={len(result)} matched={matched} pending={pending}")


if __name__ == "__main__":
    main()
