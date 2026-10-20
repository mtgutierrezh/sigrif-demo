import { useQuery } from "@tanstack/react-query";
import type { Feature, FeatureCollection, MultiPolygon } from "geojson";

export interface RiskClassProperties {
  risk_level: string;
  area_ha: number;
  polygons: number;
}

export type RiskClassFeature = Feature<MultiPolygon, RiskClassProperties>;
export type RiskSurfaceCollection = FeatureCollection<MultiPolygon, RiskClassProperties>;

export function useRiskSurface() {
  return useQuery({
    queryKey: ["risk-surface"],
    queryFn: async () => {
      const response = await fetch("/geo/risk_surface.geojson");
      if (!response.ok) {
        throw new Error("No se pudo cargar la superficie de riesgo");
      }
      return (await response.json()) as RiskSurfaceCollection;
    },
    staleTime: Infinity,
  });
}
