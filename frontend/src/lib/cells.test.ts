import { describe, expect, it } from "vitest";

import type { CellProperties } from "../features/zones/useCells";
import { buildCellsBboxPath } from "../features/zones/useCells";
import { cellColor, cellFuelSum, cellStyle, cellZoneLabel } from "./cells";

const CELL: CellProperties = {
  h3: "88b2c40825fffff",
  zone_id: 7,
  comuna: "Valparaíso",
  provincia: "Valparaíso",
  zone_name: "SECTOR CENTRO",
  dominant_fuel: "Matorral",
  fuel_native: 0.2,
  fuel_plantation: 0.1,
  fuel_shrub: 0.3,
  fuel_grass: 0.1,
  fuel_agriculture: 0.05,
  fuel_urban: 0.0,
  slope: 21.5,
  historical_fires: 4,
  wui_distance_m: 120,
  fire_probability: 0.61,
  fire_risk_level: "Alto",
  fire_model_version: "crispdm-rf-1.0",
  fire_scored_at: "2026-11-14T00:00:00+00:00",
  updated_at: "2026-11-14T00:00:00+00:00",
};

describe("cells helpers", () => {
  it("builds a bbox request with fixed precision and limit", () => {
    const path = buildCellsBboxPath(
      { minLon: -71.7, minLat: -33.1, maxLon: -71.5, maxLat: -33.0 },
      1500,
    );
    expect(path).toBe(
      "/api/v1/cells/bbox?min_lon=-71.70000&min_lat=-33.10000&max_lon=-71.50000&max_lat=-33.00000&limit=1500",
    );
  });

  it("colors cells by fuel or fire probability", () => {
    expect(cellColor(CELL, "fuel")).toBe("#b58b2a");
    expect(cellColor(CELL, "fire")).toBe("#e2664a");
  });

  it("sums wildland fuel fractions and styles the mesh", () => {
    expect(cellFuelSum(CELL)).toBeCloseTo(0.75);
    const style = cellStyle(CELL, "fuel");
    expect(style.fillColor).toBe("#b58b2a");
    expect(style.fillOpacity).toBeLessThan(0.5);
    expect(style.weight).toBeLessThan(1);
  });

  it("falls back to the comuna when the cell has no zone name", () => {
    expect(cellZoneLabel({ ...CELL, zone_name: null })).toBe("Valparaíso");
    expect(cellZoneLabel({ ...CELL, zone_name: null, comuna: null })).toBe("Sin zona");
  });
});
