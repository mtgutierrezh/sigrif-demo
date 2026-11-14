"""Asigna probabilidad histórica experimental del modelo real a la malla H3."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
H3_FILE = ROOT / "src" / "sigrif" / "data" / "h3_valparaiso_region_res8.geojson"
OOF_FILE = ROOT / "ml" / "real_oof_predictions.csv"
CSV_OUT = ROOT / "ml" / "h3_fire_scores.csv"
SQL_OUT = ROOT / "ml" / "h3_fire_scores.sql"
MODEL_VERSION = "crispdm-rf-1.0"
MEDIUM = 0.278
HIGH = 0.556


def level(probability: float) -> str:
    if probability >= HIGH:
        return "Alto"
    if probability >= MEDIUM:
        return "Medio"
    return "Bajo"


def main() -> None:
    frame = pd.read_csv(OOF_FILE)
    last_season = frame["season"].max()
    latest = frame[frame["season"] == last_season].copy()
    by_zone = {
        str(row.zone_name): float(row.p_calibrated)
        for row in latest.itertuples(index=False)
    }
    by_comuna: dict[str, float] = {}
    for comuna, group in latest.groupby("comuna"):
        by_comuna[str(comuna)] = float(median(group["p_calibrated"].tolist()))

    features = json.loads(H3_FILE.read_text(encoding="utf-8"))["features"]
    scored_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    rows: list[dict[str, object]] = []
    for feature in features:
        props = feature.get("properties") or {}
        h3 = str(props.get("h3") or "")
        zone_name = str(props.get("zone_name") or "")
        comuna = str(props.get("comuna") or "")
        probability = by_zone.get(zone_name)
        source = "zone"
        if probability is None:
            probability = by_comuna.get(comuna, 0.0)
            source = "comuna"
        probability = max(0.0, min(1.0, float(probability)))
        rows.append(
            {
                "h3": h3,
                "probability": round(probability, 6),
                "level": level(probability),
                "model_version": MODEL_VERSION,
                "scored_at": scored_at,
                "source": source,
            }
        )

    result = pd.DataFrame(rows)
    result.to_csv(CSV_OUT, index=False)
    values = ",".join(
        f"('{row.h3}',{row.probability:.6f},'{row.level}')" for row in result.itertuples()
    )
    SQL_OUT.write_text(
        "UPDATE risk_cells AS r SET "
        "fire_probability = v.p, fire_risk_level = v.l, "
        f"fire_model_version = '{MODEL_VERSION}', fire_scored_at = '{scored_at}' "
        f"FROM (VALUES {values}) AS v(h3,p,l) WHERE r.h3 = v.h3;\n",
        encoding="utf-8",
    )
    print(f"season={last_season} cells={len(result)} scored_at={scored_at}")
    print(result["level"].value_counts().to_dict())
    print(result["source"].value_counts().to_dict())


if __name__ == "__main__":
    main()
