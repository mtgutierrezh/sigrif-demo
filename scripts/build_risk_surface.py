import json
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/public/geo/forest_polygons.geojson"
OUTPUT = ROOT / "frontend/public/geo/risk_surface.geojson"

ORDER = {"Bajo": 0, "Medio": 1, "Alto": 2, "Sin dato": 3}


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    groups: dict[str, list[dict]] = {}
    for feature in data["features"]:
        level = feature["properties"].get("risk_level", "Sin dato")
        groups.setdefault(level, []).append(feature)

    features = []
    for level, items in groups.items():
        geometry = unary_union([shape(item["geometry"]) for item in items])
        geometry = geometry.simplify(0.00005, preserve_topology=True)
        area = sum(float(item["properties"].get("area_ha", 0)) for item in items)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "risk_level": level,
                    "area_ha": round(area, 1),
                    "polygons": len(items),
                },
                "geometry": mapping(geometry),
            }
        )

    features.sort(key=lambda feature: ORDER.get(feature["properties"]["risk_level"], 9))
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Superficie: {len(features)} clases, {OUTPUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
