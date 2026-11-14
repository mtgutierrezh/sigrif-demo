import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
import { GeoJSON } from "react-leaflet";

import type { CellCollection, CellProperties } from "../features/zones/useCells";
import { cellStyle, type CellColorMode } from "../lib/cells";

interface CellLayerProps {
  data: CellCollection | null | undefined;
  colorMode: CellColorMode;
}

export function CellLayer({ data, colorMode }: CellLayerProps) {
  if (!data?.features.length) {
    return null;
  }

  const first = data.features[0]?.properties.h3 ?? "none";
  const last = data.features[data.features.length - 1]?.properties.h3 ?? "none";
  const style = (feature?: Feature<Geometry>): PathOptions => {
    const properties = feature?.properties as CellProperties | undefined;
    if (!properties) {
      return { color: "#4b4b45", weight: 0.25, fillColor: "#4b4b45", fillOpacity: 0.2 };
    }
    return cellStyle(properties, colorMode);
  };

  return (
    <GeoJSON
      key={`${colorMode}-${first}-${last}-${data.features.length}`}
      data={data}
      style={style}
      interactive={false}
    />
  );
}
