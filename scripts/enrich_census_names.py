from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import shape

DATA = Path(__file__).resolve().parent.parent / "src" / "sigrif" / "data"
INPUT = DATA / "zonas_censales_valparaiso_2017.geojson"
OUTPUT = DATA / "census_names.json"
URL = "https://photon.komoot.io/reverse"


def choose_name(properties: dict[str, Any]) -> tuple[str | None, str | None]:
    district = str(properties.get("district") or "").strip()
    locality = str(properties.get("locality") or "").strip()
    name = str(properties.get("name") or "").strip()
    osm_key = str(properties.get("osm_key") or "").strip()
    if district:
        return district, "district"
    if locality:
        return locality, "locality"
    if name and osm_key in {"place", "landuse"}:
        return name, f"osm_{osm_key}"
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.05)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    cache: dict[str, Any] = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    pending = []
    for feature in data["features"]:
        properties = feature["properties"]
        comuna = str(properties.get("NOM_COMUNA") or "")
        geocode = str(properties.get("GEOCODIGO") or "")
        if comuna == "VALPARAÍSO" or not geocode or geocode in cache:
            continue
        pending.append((geocode, feature))
    if args.limit:
        pending = pending[: args.limit]

    with httpx.Client(timeout=20.0, headers={"User-Agent": "SIGRIF-academic/1.0"}) as client:
        for index, (geocode, feature) in enumerate(pending, start=1):
            point = shape(feature["geometry"]).representative_point()
            try:
                response = client.get(URL, params={"lat": point.y, "lon": point.x, "limit": 1})
                response.raise_for_status()
                payload = response.json()
                features = payload.get("features") or []
                props = features[0].get("properties", {}) if features else {}
                name, field = choose_name(props)
                cache[geocode] = {
                    "name": name,
                    "field": field,
                    "district": props.get("district"),
                    "locality": props.get("locality"),
                    "osm_name": props.get("name"),
                    "osm_key": props.get("osm_key"),
                    "osm_value": props.get("osm_value"),
                }
            except Exception as exc:
                cache[geocode] = {"name": None, "field": None, "error": str(exc)}
            if index % 25 == 0:
                OUTPUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{index}/{len(pending)}", flush=True)
            time.sleep(args.delay)
    OUTPUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    named = sum(1 for item in cache.values() if item.get("name"))
    print(f"cache={len(cache)} named={named} total={len(cache)}")


if __name__ == "__main__":
    main()
