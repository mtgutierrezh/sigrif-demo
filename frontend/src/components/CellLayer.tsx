import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
import { GeoJSON } from "react-leaflet";

import { useCells } from "../features/zones/useCells";
import { riskColor } from "../lib/risk";

export function CellLayer() {
  const { data } = useCells();

  if (!data) {
    return null;
  }

  const style = (feature?: Feature<Geometry>): PathOptions => {
    const level = (feature?.properties?.risk_level ?? "Sin dato") as Parameters<
      typeof riskColor
    >[0];
    const color = riskColor(level);
    return {
      color,
      weight: 0.5,
      opacity: 0.75,
      fillColor: color,
      fillOpacity: 0.32,
    };
  };

  const features = data.features.filter((feature) => {
    const properties = feature.properties;
    const fuel =
      properties.fuel_native +
      properties.fuel_plantation +
      properties.fuel_shrub +
      properties.fuel_grass +
      properties.fuel_agriculture;
    return fuel >= 0.1;
  });
  const filtered = { ...data, features };

  return <GeoJSON data={filtered} style={style} interactive={false} />;
}
