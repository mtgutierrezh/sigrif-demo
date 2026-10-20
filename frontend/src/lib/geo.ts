import type { Feature, FeatureCollection, MultiPolygon } from "geojson";

import type { Zone } from "../features/zones/types";

export type ZoneFeature = Feature<MultiPolygon, { id: number; name: string; risk: string }>;

export function zonesToFeatureCollection(zones: Zone[]): FeatureCollection<MultiPolygon> {
  return {
    type: "FeatureCollection",
    features: zones
      .filter((zone): zone is Zone & { geometry: MultiPolygon } => zone.geometry !== null)
      .map<ZoneFeature>((zone) => ({
        type: "Feature",
        id: zone.id,
        geometry: zone.geometry,
        properties: { id: zone.id, name: zone.name, risk: zone.risk_level },
      })),
  };
}
