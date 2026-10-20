import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
import { GeoJSON } from "react-leaflet";

import { useRiskSurface } from "../features/zones/useRiskSurface";
import { riskColor } from "../lib/risk";

export function RiskSurface() {
  const { data } = useRiskSurface();

  if (!data) {
    return null;
  }

  const style = (feature?: Feature<Geometry>): PathOptions => {
    const level = (feature?.properties?.risk_level ?? "Sin dato") as Parameters<
      typeof riskColor
    >[0];
    return {
      color: "transparent",
      weight: 0,
      fillColor: riskColor(level),
      fillOpacity: 0.55,
    };
  };

  return <GeoJSON data={data} style={style} interactive={false} />;
}
