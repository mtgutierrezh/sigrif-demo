import importlib.util
import sys
from pathlib import Path

import joblib
import numpy as np
import pytest
from shapely.geometry import box

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "crispdm_real_model.py"
SPEC = importlib.util.spec_from_file_location("crispdm_real_model", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def make_zone(index: int, x: float, y: float) -> "MODULE.Zone":
    geometry = box(x, y, x + 0.01, y + 0.01)
    properties = {
        "fuel_native": 0.1,
        "fuel_plantation": 0.1,
        "fuel_shrub": 0.1,
        "fuel_grass": 0.1,
        "fuel_agriculture": 0.1,
        "fuel_urban": 0.5,
        "vegetation": 0.4,
        "slope": 10.0,
        "dem_elev_media_m": 100.0,
        "dem_elev_min_m": 80.0,
        "dem_elev_max_m": 120.0,
        "Población": 1000,
        "dominant_fuel": "Urbano",
    }
    return MODULE.Zone(
        index=index,
        zone_id=f"Z{index:04d}",
        name=f"Zona {index}",
        comuna="Comuna A" if index == 0 else "Comuna B",
        provincia="Provincia A" if index == 0 else "Provincia B",
        zone_type="zona_censal",
        geometry=geometry,
        area_km2=MODULE.geometry_area_km2(geometry),
        centroid_lon=float(geometry.centroid.x),
        centroid_lat=float(geometry.centroid.y),
        properties=properties,
    )


def small_dataset():
    zones = [make_zone(0, -71.0, -33.0), make_zone(1, -70.9, -33.0)]
    seasons = ["2010_2011", "2011_2012", "2012_2013"]
    counts = MODULE.empty_counts(zones, seasons)
    counts[(0, "2010_2011")] = {"n": 1, "area_ha": 2.0}
    counts[(0, "2012_2013")] = {"n": 1, "area_ha": 1.0}
    return zones, seasons, counts


def test_fire_next_season_label_and_history_are_separate():
    zones, seasons, counts = small_dataset()
    rows = MODULE.build_dataset_rows(zones, seasons, counts)
    row_2011_zone0 = next(
        row for row in rows if row["season"] == "2011_2012" and row["zone_id"] == "Z0000"
    )
    row_2011_zone1 = next(
        row for row in rows if row["season"] == "2011_2012" and row["zone_id"] == "Z0001"
    )
    row_2012_zone0 = next(
        row for row in rows if row["season"] == "2012_2013" and row["zone_id"] == "Z0000"
    )
    assert row_2011_zone0[MODULE.TARGET] == 0
    assert row_2011_zone1[MODULE.TARGET] == 0
    assert row_2012_zone0[MODULE.TARGET] == 1
    assert row_2011_zone0["prior_fires_last1_log"] == pytest.approx(np.log1p(1))
    assert row_2011_zone1["prior_fires_last1_log"] == 0.0
    assert row_2012_zone0["prior_fires_last3_log"] == pytest.approx(np.log1p(1))


def test_no_temporal_leakage_from_target_or_future_season():
    zones, seasons, counts = small_dataset()
    before = MODULE.build_dataset_rows(zones, seasons, counts)
    target_row_before = next(
        row for row in before if row["season"] == "2011_2012" and row["zone_id"] == "Z0000"
    )
    counts[(0, "2011_2012")] = {"n": 5, "area_ha": 99.0}
    counts[(0, "2012_2013")] = {"n": 8, "area_ha": 120.0}
    after = MODULE.build_dataset_rows(zones, seasons, counts)
    target_row_after = next(
        row for row in after if row["season"] == "2011_2012" and row["zone_id"] == "Z0000"
    )
    for feature in MODULE.NUMERIC_BASE + MODULE.CATEGORICAL_BASE:
        assert target_row_after[feature] == target_row_before[feature]
    assert target_row_after["n_fires_target"] == 5
    assert target_row_after[MODULE.TARGET] == 1


def test_prior_season_fire_changes_next_season_features():
    zones, seasons, counts = small_dataset()
    before = MODULE.build_dataset_rows(zones, seasons, counts)
    row_before = next(
        row for row in before if row["season"] == "2011_2012" and row["zone_id"] == "Z0001"
    )
    counts[(1, "2010_2011")] = {"n": 3, "area_ha": 7.0}
    after = MODULE.build_dataset_rows(zones, seasons, counts)
    row_after = next(
        row for row in after if row["season"] == "2011_2012" and row["zone_id"] == "Z0001"
    )
    assert row_before["prior_fires_last1_log"] == 0.0
    assert row_after["prior_fires_last1_log"] == pytest.approx(np.log1p(3))
    assert row_after[MODULE.TARGET] == 0


def test_loso_splits_cover_each_season_once_without_overlap():
    zones, seasons, counts = small_dataset()
    rows = MODULE.build_dataset_rows(zones, seasons, counts)
    folds = MODULE.make_loso_splits(rows)
    assert len(folds) == len(seasons) - 1
    tested = []
    for fold in folds:
        train = set(fold["train"])
        test = set(fold["test"])
        assert train.isdisjoint(test)
        assert len(test) == len(zones)
        tested.extend(test)
    assert sorted(tested) == list(range(len(rows)))
    assert len(set(tested)) == len(tested)


def test_spatial_province_splits_are_group_disjoint():
    zones, seasons, counts = small_dataset()
    rows = MODULE.build_dataset_rows(zones, seasons, counts)
    folds = MODULE.make_province_splits(rows)
    assert len(folds) == 2
    for fold in folds:
        train_provinces = {rows[index]["provincia"] for index in fold["train"]}
        test_provinces = {rows[index]["provincia"] for index in fold["test"]}
        assert train_provinces.isdisjoint(test_provinces)
        assert test_provinces == {fold["test_group"]}


def test_metrics_perfect_predictions_and_baseline():
    y = [0, 0, 1, 1]
    probabilities = [0.05, 0.10, 0.85, 0.90]
    metrics = MODULE.binary_metrics(y, probabilities)
    assert metrics["pr_auc"] == pytest.approx(1.0)
    assert metrics["roc_auc"] == pytest.approx(1.0)
    assert metrics["brier"] < 0.05
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["tp"] == 2 and metrics["tn"] == 2


def test_thresholds_are_justified_not_argmax():
    y = [0, 0, 0, 1, 1, 1, 1, 1]
    probabilities = [0.01, 0.05, 0.10, 0.20, 0.40, 0.70, 0.80, 0.90]
    balanced = MODULE.threshold_max_f1(y, probabilities)
    high_precision = MODULE.threshold_for_precision(y, probabilities, 0.70)
    high_recall = MODULE.threshold_for_recall(y, probabilities, 0.80)
    assert 0.0 <= balanced["threshold"] <= 1.0
    assert balanced["f1"] >= 0.5
    assert high_precision["precision"] >= 0.70
    assert high_recall["recall"] >= 0.80
    assert high_precision["threshold"] >= high_recall["threshold"]


def test_calibration_curve_and_nan_filtering():
    y = [0, 0, 1, 1]
    probabilities = [0.05, 0.20, np.nan, 0.90]
    curve = MODULE.calibration_curve_data([0, 0, 1, 1], [0.05, 0.20, 0.60, 0.90], bins=2)
    assert len(curve["bins"]) == 2
    assert 0.0 <= curve["ece"] <= 1.0
    metrics = MODULE.binary_metrics(y, probabilities)
    assert metrics["n"] == 3


def test_season_climate_dry_spell_crosses_month_boundary():
    daily = {}
    precip = [0.0, 0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    for index, value in enumerate(precip, start=1):
        day = MODULE.date(2010, 7, index)
        daily[day] = {
            "temperature_2m_mean": 15.0,
            "precipitation_sum": value,
            "relative_humidity_2m_mean": 70.0,
            "wind_speed_10m_max": 10.0,
            "et0_fao_evapotranspiration": 2.0,
        }
    result = MODULE._season_climate(daily, "2010_2011")
    assert result["dry_days"] == 9
    assert result["max_dry_spell"] == 5
    assert result["precip_mm"] == pytest.approx(5.0)
    assert result["n_days"] == 10


def test_region_filter_accepts_old_new_and_float_codes():
    assert MODULE._record_region({"CODREG": "05"})
    assert MODULE._record_region({"CODREG": 5.0})
    assert MODULE._record_region({"REGION": "Valparaíso"})
    assert MODULE._record_region({"REGION": "Valparaiso"})
    assert not MODULE._record_region({"CODREG": "08"})
    assert not MODULE._record_region({"REGION": "Biobío"})


def test_preprocessor_and_joblib_artifact_roundtrip(tmp_path):
    rows = [
        {"a": 1.0, "b": None, "c": "x"},
        {"a": 2.0, "b": 3.0, "c": "y"},
        {"a": None, "b": 4.0, "c": "x"},
        {"a": 5.0, "b": 6.0, "c": None},
    ]
    pipeline = MODULE.build_model_pipeline(
        "logistic_regression",
        ["a", "b"],
        ["c"],
        seed=42,
        quick=True,
    )
    y = [0, 1, 0, 1]
    pipeline.fit(rows, y)
    before = pipeline.predict_proba(rows)
    path = tmp_path / "tiny_model.joblib"
    joblib.dump({"model": pipeline, "target": MODULE.TARGET}, path)
    loaded = joblib.load(path)
    after = loaded["model"].predict_proba(rows)
    assert np.allclose(before, after)
    assert loaded["target"] == MODULE.TARGET
    names = pipeline.named_steps["preprocess"].get_feature_names_out()
    assert any("cat__c" in str(name) for name in names)


def test_feature_spec_excludes_target_and_future_aggregates():
    features = set(MODULE.NUMERIC_BASE + MODULE.CATEGORICAL_BASE)
    assert MODULE.TARGET not in features
    assert "n_fires_target" not in features
    assert "season" not in features
    assert "historical_fires" not in features
    assert not any(name.startswith("incendios_") for name in features)
