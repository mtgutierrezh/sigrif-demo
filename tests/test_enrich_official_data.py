"""Pruebas del enriquecimiento oficial, sin llamadas de red reales."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import httpx
import numpy as np
import pytest
from shapely.geometry import Polygon

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "enrich_official_data.py"
SPEC = importlib.util.spec_from_file_location("enrich_official_data", MODULE_PATH)
assert SPEC and SPEC.loader
enrich = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = enrich
SPEC.loader.exec_module(enrich)

ZONE = Polygon(
    [
        (-71.0000, -33.0000),
        (-71.0000, -32.9900),
        (-70.9900, -32.9900),
        (-70.9900, -33.0000),
        (-71.0000, -33.0000),
    ]
)
LEFT_HALF = Polygon(
    [
        (-71.0000, -33.0000),
        (-71.0000, -32.9900),
        (-70.9950, -32.9900),
        (-70.9950, -33.0000),
        (-71.0000, -33.0000),
    ]
)
RIGHT_HALF = Polygon(
    [
        (-70.9950, -33.0000),
        (-70.9950, -32.9900),
        (-70.9900, -32.9900),
        (-70.9900, -33.0000),
        (-70.9950, -33.0000),
    ]
)


def _feature() -> dict:
    return {
        "type": "Feature",
        "geometry": ZONE.__geo_interface__,
        "properties": {
            "Nombre_Cer": "ZONA TEST",
            "Comuna": "Valparaíso",
            "vegetation": 0.35,
            "historical_fires": 5,
            "slope": 20.0,
        },
    }


def _polygon(geometry: Polygon, uso: str, subuso: str, object_id: int = 1):
    return enrich.ConafPolygon(
        object_id=object_id,
        uso=uso,
        subuso=subuso,
        nom_com="Valparaíso",
        geometry=geometry,
    )


def _arcgis_polygon(ring: list[list[float]], object_id: int = 1) -> dict:
    return {
        "attributes": {
            "OBJECTID": object_id,
            "USO": "Bosques",
            "SUBUSO": "Bosque Nativo",
            "SUPERF_HA": 1.0,
            "NOM_COM": "Valparaíso",
        },
        "geometry": {"rings": [ring]},
    }


def test_utm_roundtrip_is_centimetric():
    lon, lat = -71.5, -33.05
    east, north = enrich.lonlat_to_utm_arrays(np.array([lon]), np.array([lat]))
    back_lon, back_lat = enrich.utm_to_lonlat(float(east[0]), float(north[0]))
    assert back_lon == pytest.approx(lon, abs=1e-7)
    assert back_lat == pytest.approx(lat, abs=1e-7)


def test_rings_to_geometry_keeps_hole():
    outer = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]
    inner = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]]
    geometry = enrich.rings_to_geometry([outer, inner])
    assert geometry.area == pytest.approx(100 - 16)


def test_category_weights_mixed_uses_halves():
    assert enrich.category_weights("Praderas y Matorrales", "Matorral-Pradera") == {
        "matorral": 0.5,
        "pradera": 0.5,
    }
    assert enrich.category_weights("Terrenos Agrícolas", "Rotación Cultivo-Pradera") == {
        "agricola": 0.5,
        "pradera": 0.5,
    }
    assert enrich.category_weights("Desconocido", "X") == {"otro": 1.0}


def test_conaf_fractions_clips_polygons_to_zone():
    polygons = [
        _polygon(LEFT_HALF, "Bosques", "Bosque Nativo", 1),
        _polygon(RIGHT_HALF, "Bosques", "Plantación", 2),
        _polygon(
            Polygon(
                [
                    (-70.9800, -33.0000),
                    (-70.9800, -32.9900),
                    (-70.9700, -32.9900),
                    (-70.9700, -33.0000),
                    (-70.9800, -33.0000),
                ]
            ),
            "Áreas Urbanas e Industriales",
            "Ciudades, Pueblos, Zonas Industriales",
            3,
        ),
    ]
    fractions = enrich.conaf_fractions(ZONE, polygons)
    assert fractions is not None
    assert fractions["bosque_nativo"] == pytest.approx(0.5, abs=1e-4)
    assert fractions["plantacion"] == pytest.approx(0.5, abs=1e-4)
    assert fractions["urbano"] == pytest.approx(0.0)
    assert fractions["cobertura"] == pytest.approx(1.0, abs=1e-4)
    assert fractions["poligonos"] == 2


def test_conaf_fractions_without_intersection_returns_none():
    outside = Polygon(
        [
            (-70.9, -33.0),
            (-70.9, -32.99),
            (-70.89, -32.99),
            (-70.89, -33.0),
            (-70.9, -33.0),
        ]
    )
    assert enrich.conaf_fractions(ZONE, [_polygon(outside, "Bosques", "Bosque Nativo")]) is None


def test_slope_from_samples_recovers_plane():
    lons = np.array([-71.000, -70.998, -71.000, -70.998])
    lats = np.array([-33.000, -33.000, -32.998, -32.998])
    east, north = enrich.lonlat_to_utm_arrays(lons, lats)
    elevations = 100.0 + 0.10 * (east - east.mean()) + 0.05 * (north - north.mean())
    points = list(zip(lons, lats, strict=True))
    slope = enrich.slope_from_samples(points, list(elevations))
    expected = math.degrees(math.atan(math.hypot(0.10, 0.05)))
    assert slope == pytest.approx(expected, abs=0.01)


def test_slope_with_insufficient_points_returns_none():
    assert enrich.slope_from_samples([(-71.0, -33.0)], [100.0]) is None


def test_count_fires_by_zone_includes_boundary():
    left = Polygon(
        [
            (-71.00, -33.00),
            (-71.00, -32.99),
            (-70.995, -32.99),
            (-70.995, -33.00),
            (-71.00, -33.00),
        ]
    )
    right = Polygon(
        [
            (-70.995, -33.00),
            (-70.995, -32.99),
            (-70.99, -32.99),
            (-70.99, -33.00),
            (-70.995, -33.00),
        ]
    )
    points = [
        enrich.FirePoint(lon=-70.997, lat=-32.995, season="2024_2025"),
        enrich.FirePoint(lon=-70.995, lat=-32.995, season="2010_2011"),
        enrich.FirePoint(lon=-70.980, lat=-32.995, season="2020_2021"),
    ]
    counts, seasons, latest, last_five = enrich.count_fires_by_zone([left, right], points)
    assert counts == [2, 1]
    assert seasons == [2, 1]
    assert latest == ["2024_2025", "2010_2011"]
    assert last_five == [1, 0]


def test_enrich_features_marks_fallback_when_sources_missing():
    features, stats = enrich.enrich_features(
        [_feature()],
        source="all",
        updated="2026-11-13",
        conaf_polygons=None,
        fire_points=None,
        dem_samples=None,
    )
    props = features[0]["properties"]
    assert props["vegetation"] == 0.35
    assert props["historical_fires"] == 5
    assert props["slope"] == 20.0
    assert props["Estado_Vegetacion"] == "pendiente"
    assert props["Estado_Incendios"] == "pendiente"
    assert props["Estado_Pendiente"] == "pendiente"
    assert "no disponible" in props["Fuente_Vegetacion"]
    assert "no disponible" in props["Fuente_Incendios"]
    assert "no disponible" in props["Fuente_Pendiente"]
    assert stats["conaf_sin_cobertura"] == 1
    assert stats["incendios_pendientes"] == 1
    assert stats["dem_pendientes"] == 1
    assert stats["dem_fallback"] == 1


def test_enrich_features_uses_official_values():
    points = [
        (-71.000, -33.000),
        (-70.998, -33.000),
        (-71.000, -32.998),
        (-70.998, -32.998),
    ]
    east, north = enrich.lonlat_to_utm_arrays(
        np.array([point[0] for point in points]),
        np.array([point[1] for point in points]),
    )
    elevations = 100.0 + 0.10 * (east - east.mean()) + 0.05 * (north - north.mean())
    sample = enrich.DemSample(points=points, elevations=list(elevations))

    features, stats = enrich.enrich_features(
        [_feature()],
        source="all",
        updated="2026-11-13",
        conaf_polygons=[_polygon(LEFT_HALF, "Bosques", "Bosque Nativo")],
        fire_points=[enrich.FirePoint(lon=-70.997, lat=-32.995, season="2024_2025")],
        dem_samples={enrich._zone_key(ZONE): sample},
    )
    props = features[0]["properties"]
    assert props["vegetation"] == pytest.approx(0.5, abs=1e-4)
    assert props["historical_fires"] == 1
    assert props["incendios_temporadas"] == 1
    assert props["slope"] == pytest.approx(
        math.degrees(math.atan(math.hypot(0.10, 0.05))), abs=0.01
    )
    assert props["Estado_Vegetacion"] == "oficial"
    assert props["Estado_Incendios"] == "oficial"
    assert props["Estado_Pendiente"] == "oficial_aproximado"
    assert props["Datos_Actualizados"] == "2026-11-13"
    assert stats["conaf_con_cobertura"] == 1
    assert stats["incendios_asignados"] == 1
    assert stats["dem_con_pendiente"] == 1


def test_load_conaf_region_paginates_and_caches(tmp_path: Path):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["resultOffset"])
        calls.append(offset)
        ring = [[-71.0, -33.0], [-71.0, -32.99], [-70.99, -32.99], [-70.99, -33.0]]
        if offset == 0:
            return httpx.Response(
                200,
                json={
                    "features": [_arcgis_polygon(ring, 1)],
                    "exceededTransferLimit": True,
                },
            )
        return httpx.Response(
            200,
            json={
                "features": [_arcgis_polygon(ring, 2)],
                "exceededTransferLimit": False,
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        polygons = enrich.load_conaf_region(client, tmp_path, log=lambda *_args: None)
    assert calls == [0, 1]
    assert len(polygons) == 2
    assert (tmp_path / "conaf" / "valparaiso_uso_suelo.geojson").exists()

    def fail(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no debe consultar la red si hay cache")

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        cached = enrich.load_conaf_region(client, tmp_path, log=lambda *_args: None)
    assert len(cached) == 2


def test_dem_batch_and_cache_use_mock_transport(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(enrich, "SRTM_MIN_INTERVAL", 0.0)

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.url.params["locations"]
        locations = raw.split("|")
        return httpx.Response(
            200,
            json={
                "results": [
                    {"location": location, "elevation": 100.0 + index}
                    for index, location in enumerate(locations)
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        samples = enrich.load_dem_samples(client, [ZONE], tmp_path, log=lambda *_args: None)
    key = enrich._zone_key(ZONE)
    assert key in samples
    assert len(samples[key].points) >= 6
    assert all(value is not None for value in samples[key].elevations)
    assert (tmp_path / "dem" / "srtm_samples.json").exists()

    def fail(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no debe consultar la red si hay cache")

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        cached = enrich.load_dem_samples(client, [ZONE], tmp_path, log=lambda *_args: None)
    assert len(cached[key].points) == len(samples[key].points)
    assert cached[key].points[0] == pytest.approx(samples[key].points[0])


def test_write_geojson_roundtrip(tmp_path: Path):
    output = tmp_path / "out.geojson"
    payload = {
        "type": "FeatureCollection",
        "name": "test",
        "features": [_feature()],
    }
    enrich._write_json_atomic(output, payload, compact=True)
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["type"] == "FeatureCollection"
    assert loaded["features"][0]["properties"]["Nombre_Cer"] == "ZONA TEST"


def test_read_fire_shapefile_utm(tmp_path: Path):
    import shapefile

    east, north = enrich.lonlat_to_utm_arrays(np.array([-71.5]), np.array([-33.05]))
    shp = tmp_path / "fires.shp"
    writer = shapefile.Writer(str(shp), shapeType=shapefile.POINT)
    writer.field("NOM_INCEN", "C", size=40)
    writer.field("COMUNA", "C", size=30)
    writer.field("CAUSA_GENE", "C", size=40)
    writer.point(float(east[0]), float(north[0]))
    writer.record("INCENDIO TEST", "VALPARAISO", "NATURAL")
    writer.close()
    shp.with_suffix(".prj").write_text(
        'PROJCS["WGS_1984_UTM_Zone_19S",GEOGCS["GCS_WGS_1984"],PROJECTION["Transverse_Mercator"]]',
        encoding="utf-8",
    )
    points = enrich._read_fire_shapefile(shp, "2020_2021")
    assert len(points) == 1
    assert points[0].lon == pytest.approx(-71.5, abs=1e-6)
    assert points[0].lat == pytest.approx(-33.05, abs=1e-6)
    assert points[0].nombre == "INCENDIO TEST"


def test_read_fire_shapefile_filters_outside_region(tmp_path: Path):
    import shapefile

    shp = tmp_path / "outside.shp"
    writer = shapefile.Writer(str(shp), shapeType=shapefile.POINT)
    writer.field("NOM_INCEN", "C", size=40)
    writer.point(-70.0, -20.0)
    writer.record("FUERA")
    writer.close()
    shp.with_suffix(".prj").write_text(
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984"]]', encoding="utf-8"
    )
    assert enrich._read_fire_shapefile(shp, "2020_2021") == []


def test_dem_failure_does_not_cache_empty_sample(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(enrich, "SRTM_MIN_INTERVAL", 0.0)

    def boom(*_args, **_kwargs):
        raise RuntimeError("sin red")

    monkeypatch.setattr(enrich, "request_json", boom)
    transport = httpx.MockTransport(lambda _request: httpx.Response(500))
    with httpx.Client(transport=transport) as client:
        samples = enrich.load_dem_samples(client, [ZONE], tmp_path, log=lambda *_args: None)
    key = enrich._zone_key(ZONE)
    assert samples[key].points == []
    cache = json.loads((tmp_path / "dem" / "srtm_samples.json").read_text(encoding="utf-8"))
    assert key not in cache["zonas"]


def test_dem_cache_preserves_other_zones(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(enrich, "SRTM_MIN_INTERVAL", 0.0)

    def handler(request: httpx.Request) -> httpx.Response:
        locations = request.url.params["locations"].split("|")
        return httpx.Response(
            200,
            json={"results": [{"location": loc, "elevation": 50.0} for loc in locations]},
        )

    other = Polygon(
        [
            (-71.01, -33.01),
            (-71.01, -33.00),
            (-71.00, -33.00),
            (-71.00, -33.01),
            (-71.01, -33.01),
        ]
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        enrich.load_dem_samples(client, [ZONE], tmp_path, log=lambda *_args: None)
        enrich.load_dem_samples(client, [other], tmp_path, log=lambda *_args: None)
    cache = json.loads((tmp_path / "dem" / "srtm_samples.json").read_text(encoding="utf-8"))
    assert enrich._zone_key(ZONE) in cache["zonas"]
    assert enrich._zone_key(other) in cache["zonas"]
