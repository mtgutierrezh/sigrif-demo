import type { PathOptions } from "leaflet";

import type { CellProperties } from "../features/zones/useCells";
import { fuelColor } from "./fuel";
import { riskColor } from "./risk";
import type { RiskLevel } from "../features/zones/types";

export type CellColorMode = "fuel" | "fire";

export function cellFuelSum(properties: CellProperties): number {
  return (
    properties.fuel_native +
    properties.fuel_plantation +
    properties.fuel_shrub +
    properties.fuel_grass +
    properties.fuel_agriculture
  );
}

export function cellColor(properties: CellProperties, mode: CellColorMode): string {
  if (mode === "fuel") {
    return fuelColor(properties.dominant_fuel);
  }
  return riskColor(properties.fire_risk_level as RiskLevel);
}

export function cellStyle(properties: CellProperties, mode: CellColorMode): PathOptions {
  const color = cellColor(properties, mode);
  return {
    color,
    weight: 0.25,
    opacity: 0.4,
    fillColor: color,
    fillOpacity: 0.28,
  };
}

export function cellZoneLabel(properties: CellProperties): string {
  return properties.zone_name ?? properties.comuna ?? "Sin zona";
}
