import json

from shapely.geometry import Polygon

from sigrif.h3_mesh import (
    FUEL_LABELS,
    _fuel_class,
    _screening_score,
    build_mesh,
    geometry_dict,
)


def _square(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [min_lon, max_lat],
                [max_lon, max_lat],
                [max_lon, min_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def _write(path, features):
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )


def _zone(name: str, geometry, comuna: str = "Valparaíso"):
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "name": name,
            "Comuna": comuna,
            "Provincia": "Valparaíso",
            "slope": 22.0,
            "historical_fires": 5,
            "fuel_native": 0.4,
            "fuel_plantation": 0.1,
            "fuel_shrub": 0.5,
            "fuel_grass": 0.0,
            "fuel_agriculture": 0.0,
            "fuel_urban": 0.0,
            "dominant_fuel": "Matorral",
        },
    }


def test_fuel_class_maps_conaf_categories():
    assert _fuel_class("Bosques", "Bosque Nativo") == "native"
    assert _fuel_class("Bosques", "Plantación") == "plantation"
    assert _fuel_class("Praderas y Matorrales", "Matorral") == "shrub"
    assert _fuel_class("Praderas y Matorrales", "Praderas") == "grass"
    assert _fuel_class("Terrenos Agrícolas", "Terreno de Uso Agrícola") == "agriculture"
    assert _fuel_class("Áreas Urbanas e Industriales", "Ciudades") == "urban"
    assert _fuel_class("Cuerpos de Agua", "Ríos") is None


def test_screening_score_uses_fuel_slope_and_fires():
    level, score = _screening_score(
        {
            "native": 1.0,
            "plantation": 0.0,
            "shrub": 0.0,
            "grass": 0.0,
            "agriculture": 0.0,
            "urban": 0.0,
        },
        30.0,
        8,
    )
    assert level == "Alto"
    assert 0.7 <= score <= 0.95
    level, score = _screening_score(
        {
            "native": 0.0,
            "plantation": 0.0,
            "shrub": 0.0,
            "grass": 0.0,
            "agriculture": 0.0,
            "urban": 1.0,
        },
        2.0,
        0,
    )
    assert level == "Bajo"
    assert score < 0.4


def test_geometry_dict_returns_closed_polygon():
    polygon = Polygon([(-71.0, -33.0), (-71.0, -33.1), (-70.9, -33.1), (-71.0, -33.0)])
    payload = geometry_dict(polygon, precision=5)
    assert payload["type"] == "Polygon"
    assert payload["coordinates"][0][0] == payload["coordinates"][0][-1]
    assert payload["coordinates"][0][0] == [-71.0, -33.0]


def test_build_mesh_region_assigns_zone_and_geometry(tmp_path):
    comunas = tmp_path / "comunas.geojson"
    zones = tmp_path / "zones.geojson"
    _write(
        comunas,
        [
            {
                "type": "Feature",
                "geometry": _square(-71.0, -33.0, -70.98, -32.98),
                "properties": {"comuna": "Valparaíso", "provincia": "Valparaíso"},
            }
        ],
    )
    _write(
        zones,
        [
            _zone("SECTOR CENTRO", _square(-70.995, -32.995, -70.985, -32.985)),
            _zone("SECTOR NORTE", _square(-70.99, -32.99, -70.985, -32.985)),
        ],
    )

    features, metadata = build_mesh(
        zones_path=zones,
        comunas_path=comunas,
        conaf_path=None,
        fires_path=None,
        resolution=9,
        scope="region",
    )

    assert metadata["cells_total"] == len(features)
    assert metadata["cells_total"] > 5
    assert metadata["duplicates_dropped"] == 0
    assert metadata["comunas_with_cells"] == 1
    assert len({feature["properties"]["h3"] for feature in features}) == len(features)
    for feature in features:
        properties = feature["properties"]
        assert feature["geometry"]["type"] == "Polygon"
        assert properties["zone_id"] is not None
        assert properties["zone_name"]
        assert properties["comuna"] == "Valparaíso"
        assert properties["provincia"] == "Valparaíso"
        assert properties["dominant_fuel"] in FUEL_LABELS.values()
        assert properties["risk_level"] in {"Bajo", "Medio", "Alto"}
        assert properties["zone_match"] in {"intersect", "nearest"}


def test_build_mesh_zones_scope_only_returns_zone_cells(tmp_path):
    zones = tmp_path / "zones.geojson"
    comunas = tmp_path / "comunas.geojson"
    _write(zones, [_zone("SECTOR CENTRO", _square(-71.0, -33.0, -70.99, -32.99))])
    _write(comunas, [])

    features, metadata = build_mesh(
        zones_path=zones,
        comunas_path=comunas,
        conaf_path=None,
        fires_path=None,
        resolution=9,
        scope="zones",
    )

    assert features
    assert metadata["scope"] == "zonas_oficiales"
    assert metadata["cells_in_zone"] == len(features)
    assert all(feature["properties"]["zone_match"] == "intersect" for feature in features)


def test_build_mesh_deduplicates_overlapping_comunas(tmp_path):
    comunas = tmp_path / "comunas.geojson"
    zones = tmp_path / "zones.geojson"
    geometry = _square(-71.0, -33.0, -70.99, -32.99)
    _write(
        comunas,
        [
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {"comuna": "Valparaíso", "provincia": "Valparaíso"},
            },
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {"comuna": "Valparaíso", "provincia": "Valparaíso"},
            },
        ],
    )
    _write(zones, [_zone("SECTOR CENTRO", geometry)])

    features, metadata = build_mesh(
        zones_path=zones,
        comunas_path=comunas,
        conaf_path=None,
        fires_path=None,
        resolution=9,
        scope="region",
    )

    assert metadata["duplicates_dropped"] > 0
    assert len({feature["properties"]["h3"] for feature in features}) == len(features)
