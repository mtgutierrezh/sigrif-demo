"""Construye la capa híbrida: 54 sectores urbanos + comunas continentales.

Las comunas usan los polígonos DPA 2022 (IDE Minagri/MINVU). Los atributos
estáticos que el modelo necesita para las comunas son un prior académico
provincial explícito, porque el catastro CONAF y el DEM se incorporarán en la
siguiente fase. No se presentan como mediciones oficiales.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "src" / "sigrif" / "data"
CITY = DATA / "cerros_sectores.geojson"
DPA = DATA / "dpa_valparaiso_2022.geojson"
OUT = DATA / "cerros_sectores_valparaiso_dpa.geojson"


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


def _features(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def main() -> None:
    city = _features(CITY)
    dpa = _features(DPA)
    regional: list[dict[str, Any]] = []

    for feature in city:
        props = dict(feature.get("properties") or {})
        props["Comuna"] = "Valparaíso"
        props["Provincia"] = "Valparaíso"
        props["Nivel"] = "sector"
        props["vegetation"] = 0.35
        props["historical_fires"] = 5
        props["slope"] = 20.0
        props["Fuente_Geometria"] = "SIG Municipalidad de Valparaíso"
        regional.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})

    for feature in dpa:
        props = dict(feature.get("properties") or {})
        comuna = str(props.get("comuna") or "").strip()
        if not comuna or comuna in {"Valparaíso", "Juan Fernández", "Isla de Pascua"}:
            continue
        provincia = str(props.get("provincia") or "").strip()
        vegetation, fires, slope = PRIORS.get(provincia, (0.30, 4, 20.0))
        regional.append(
            {
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": {
                    "Nombre_Cer": comuna,
                    "Comuna": comuna,
                    "Provincia": provincia,
                    "Nivel": "comunal",
                    "Superficie_km2": props.get("superficie"),
                    "vegetation": vegetation,
                    "historical_fires": fires,
                    "slope": slope,
                    "Fuente_Geometria": "DPA 2022, IDE Minagri/MINVU",
                },
            }
        )

    payload = {
        "type": "FeatureCollection",
        "name": "sigrif_regional_valparaiso",
        "features": regional,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Zonas: {len(regional)} (sectores={len(city)}, comunas={len(regional) - len(city)})")
    print(OUT)


if __name__ == "__main__":
    main()
