import { useQuery } from "@tanstack/react-query";
import type { Feature, FeatureCollection, Polygon } from "geojson";

import { fetchJson } from "../../lib/api";

export interface CellProperties {
  h3: string;
  dominant_fuel: string;
  fuel_native: number;
  fuel_plantation: number;
  fuel_shrub: number;
  fuel_grass: number;
  fuel_agriculture: number;
  fuel_urban: number;
  wui_distance_m: number;
  risk_level: string;
  risk_score: number;
  updated_at: string;
}

export type CellFeature = Feature<Polygon, CellProperties>;
export type CellCollection = FeatureCollection<Polygon, CellProperties>;

export function useCells() {
  return useQuery({
    queryKey: ["cells"],
    queryFn: () => fetchJson<CellCollection>("/api/v1/cells"),
    staleTime: 5 * 60 * 1000,
  });
}
