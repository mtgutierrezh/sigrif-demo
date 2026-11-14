"""Genera la malla H3 res 8 de la Región de Valparaíso continental.

Ejemplos:
    uv run python scripts/build_h3_region.py
    uv run python scripts/build_h3_region.py --scope zones
    uv run python scripts/build_h3_region.py --no-conaf --no-fires
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sigrif.h3_mesh import (
    DEFAULT_COMUNAS,
    DEFAULT_CONAF,
    DEFAULT_FIRES,
    DEFAULT_ZONES,
    REGIONAL_OUTPUT,
    ZONES_OUTPUT,
    build_mesh,
    build_payload,
    write_payload,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["region", "zones"], default="region")
    parser.add_argument("--resolution", type=int, default=8)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--zones", type=Path, default=DEFAULT_ZONES)
    parser.add_argument("--comunas", type=Path, default=DEFAULT_COMUNAS)
    parser.add_argument("--conaf", type=Path, default=DEFAULT_CONAF)
    parser.add_argument("--fires", type=Path, default=DEFAULT_FIRES)
    parser.add_argument("--no-conaf", action="store_true")
    parser.add_argument("--no-fires", action="store_true")
    parser.add_argument("--no-zone-fallback", action="store_true")
    parser.add_argument("--min-fraction", type=float, default=0.02)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output or (REGIONAL_OUTPUT if args.scope == "region" else ZONES_OUTPUT)
    features, metadata = build_mesh(
        zones_path=args.zones,
        comunas_path=args.comunas,
        conaf_path=None if args.no_conaf else args.conaf,
        fires_path=None if args.no_fires else args.fires,
        resolution=args.resolution,
        scope=args.scope,
        zone_fallback=not args.no_zone_fallback,
        min_fraction=args.min_fraction,
    )
    destination = write_payload(output, build_payload(features, metadata))
    summary = {
        "output": str(destination),
        "bytes": destination.stat().st_size,
        "cells": metadata["cells_total"],
        "cells_in_zone": metadata["cells_in_zone"],
        "cells_by_nearest_zone": metadata["cells_by_nearest_zone"],
        "duplicates_dropped": metadata["duplicates_dropped"],
        "comunas": metadata["comunas_with_cells"],
        "zones_covered": metadata["zones_covered"],
        "zones_coverage_pct": metadata["zones_coverage_pct"],
        "fuel_method": metadata["fuel_method"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
