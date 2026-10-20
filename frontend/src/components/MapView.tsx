import "leaflet/dist/leaflet.css";

import type { Feature, Geometry } from "geojson";
import L, { type Path, type PathOptions } from "leaflet";
import { useEffect, useMemo } from "react";
import { GeoJSON, MapContainer, TileLayer, ZoomControl, useMap } from "react-leaflet";

import type { Zone } from "../features/zones/types";
import { formatScore } from "../lib/format";
import { zonesToFeatureCollection } from "../lib/geo";
import { riskColor } from "../lib/risk";

interface MapViewProps {
  zones: Zone[];
  selectedId: number | null;
  onSelect: (zoneId: number) => void;
}

function MapFit({ zones, hasSelection }: { zones: Zone[]; hasSelection: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (hasSelection || zones.length === 0) {
      return;
    }
    const bounds = L.geoJSON(zonesToFeatureCollection(zones)).getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [hasSelection, map, zones]);

  return null;
}

function MapFocus({ zone }: { zone: Zone | null }) {
  const map = useMap();

  useEffect(() => {
    if (!zone?.geometry) {
      return;
    }
    const bounds = L.geoJSON(zone.geometry).getBounds();
    if (!bounds.isValid()) {
      return;
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      map.fitBounds(bounds, { padding: [40, 40] });
      return;
    }
    map.flyTo(bounds.getCenter(), 13, { duration: 0.6 });
  }, [map, zone]);

  return null;
}

export function MapView({ zones, selectedId, onSelect }: MapViewProps) {
  const collection = useMemo(() => zonesToFeatureCollection(zones), [zones]);
  const layerKey = useMemo(
    () => `${selectedId ?? "none"}-${zones.map((zone) => `${zone.id}:${zone.risk_score}`).join("|")}`,
    [selectedId, zones],
  );
  const selectedZone = zones.find((zone) => zone.id === selectedId) ?? null;

  const featureId = (feature?: Feature<Geometry, unknown>) =>
    Number((feature?.properties as { id?: number } | undefined)?.id);

  const style = (feature?: Feature<Geometry, unknown>): PathOptions => {
    const id = featureId(feature);
    const zone = zones.find((item) => item.id === id);
    const color = riskColor(zone?.risk_level);
    return {
      color: id === selectedId ? "#ebfc72" : color,
      weight: id === selectedId ? 2.5 : 1.5,
      opacity: 1,
      fillColor: color,
      fillOpacity: 0.24,
    };
  };

  return (
    <div className="h-full w-full" role="application" aria-label="Mapa de riesgo por zona">
      <MapContainer
        center={[-33.05, -71.5]}
        zoom={11}
        zoomControl={false}
        scrollWheelZoom
        className="h-full w-full"
      >
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution='Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics'
        />
        <ZoomControl position="bottomright" />
        <GeoJSON
          key={layerKey}
          data={collection}
          style={style}
          onEachFeature={(feature, layer) => {
            const zone = zones.find((item) => item.id === featureId(feature));
            if (!zone) {
              return;
            }
            const path = layer as Path;
            path.bindTooltip(
              `${zone.name} · ${zone.risk_level} · ${formatScore(zone.risk_score)}`,
              { sticky: true, direction: "top", className: "sigrif-tooltip" },
            );
            path.on("click", () => onSelect(zone.id));
          }}
        />
        <MapFit zones={zones} hasSelection={selectedId !== null} />
        <MapFocus zone={selectedZone} />
      </MapContainer>
    </div>
  );
}
