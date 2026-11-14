import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Feature, FeatureCollection, Polygon } from "geojson";

import { fetchJson } from "../../lib/api";

export const CELL_LIMIT = 4000;
export const CELL_MIN_ZOOM = 12;

export interface CellProperties {
  h3: string;
  zone_id: number | null;
  comuna: string | null;
  provincia: string | null;
  zone_name: string | null;
  dominant_fuel: string;
  fuel_native: number;
  fuel_plantation: number;
  fuel_shrub: number;
  fuel_grass: number;
  fuel_agriculture: number;
  fuel_urban: number;
  slope: number;
  historical_fires: number;
  wui_distance_m: number;
  risk_level: string;
  risk_score: number;
  updated_at: string | null;
}

export interface CellBBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export interface CellMeta {
  count: number;
  limit: number;
  truncated: boolean;
  bbox: [number, number, number, number];
}

export interface MapViewport {
  bbox: CellBBox;
  zoom: number;
}

export type CellFeature = Feature<Polygon, CellProperties>;
export type CellCollection = FeatureCollection<Polygon, CellProperties> & {
  meta?: CellMeta;
};

export function buildCellsBboxPath(bbox: CellBBox, limit = CELL_LIMIT): string {
  const params = new URLSearchParams({
    min_lon: bbox.minLon.toFixed(5),
    min_lat: bbox.minLat.toFixed(5),
    max_lon: bbox.maxLon.toFixed(5),
    max_lat: bbox.maxLat.toFixed(5),
    limit: String(limit),
  });
  return `/api/v1/cells/bbox?${params.toString()}`;
}

export function useCells(bbox: CellBBox | null, enabled = true, limit = CELL_LIMIT) {
  return useQuery({
    queryKey: ["cells", bbox, limit],
    queryFn: () => fetchJson<CellCollection>(buildCellsBboxPath(bbox as CellBBox, limit)),
    enabled: enabled && bbox !== null,
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  });
}
