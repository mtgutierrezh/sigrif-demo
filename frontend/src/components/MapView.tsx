import "leaflet/dist/leaflet.css";

import type { Feature, Geometry } from "geojson";
import L, { type Path, type PathOptions } from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, GeoJSON, MapContainer, Polygon, Rectangle, TileLayer, useMap } from "react-leaflet";

import { CellLayer } from "./CellLayer";
import { RiskSurface } from "./RiskSurface";
import { ZoomControl } from "./ZoomControl";

import type { CellCollection, MapViewport } from "../features/zones/useCells";
import type { Zone } from "../features/zones/types";
import { formatScore } from "../lib/format";
import { zoneLabel } from "../lib/names";
import { zonesToFeatureCollection } from "../lib/geo";
import { fuelColor } from "../lib/fuel";
import { riskColor } from "../lib/risk";

interface MapViewProps {
  zones: Zone[];
  selectedId: number | null;
  onSelect: (zoneId: number) => void;
  colorMode?: "risk" | "fuel" | "fire";
  cells?: CellCollection | null;
  showCells?: boolean;
  onViewportChange?: (viewport: MapViewport) => void;
}

const WORLD_RING: [number, number][] = [
  [-85, -180],
  [-85, 180],
  [85, 180],
  [85, -180],
  [-85, -180],
];

const REGION_HOLE: [number, number][] = [
  [-33.9, -72.4],
  [-33.9, -69.8],
  [-31.8, -69.8],
  [-31.8, -72.4],
  [-33.9, -72.4],
];

const REGION_BOUNDS: [[number, number], [number, number]] = [
  [-33.9, -72.4],
  [-31.8, -69.8],
];

const MAP_BOUNDS: [[number, number], [number, number]] = [
  [-56.0, -110.0],
  [-17.0, -66.0],
];

function MapFit({ hasSelection }: { hasSelection: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (hasSelection) {
      return;
    }
    map.fitBounds(REGION_BOUNDS, { padding: [24, 24] });
  }, [hasSelection, map]);

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
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
  }, [map, zone]);

  return null;
}

function MapViewportTracker({
  onChange,
}: {
  onChange?: (viewport: MapViewport) => void;
}) {
  const map = useMap();

  useEffect(() => {
    if (!onChange) {
      return;
    }
    const update = () => {
      const bounds = map.getBounds().pad(0.08);
      onChange({
        bbox: {
          minLon: bounds.getWest(),
          minLat: bounds.getSouth(),
          maxLon: bounds.getEast(),
          maxLat: bounds.getNorth(),
        },
        zoom: map.getZoom(),
      });
    };
    update();
    map.on("moveend", update);
    map.on("zoomend", update);
    return () => {
      map.off("moveend", update);
      map.off("zoomend", update);
    };
  }, [map, onChange]);

  return null;
}

export function MapView({
  zones,
  selectedId,
  onSelect,
  colorMode = "risk",
  cells = null,
  showCells = true,
  onViewportChange,
}: MapViewProps) {
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
    const color =
      colorMode === "fuel" ? fuelColor(zone?.dominant_fuel) : riskColor(zone?.risk_level);
    return {
      color: id === selectedId ? "#ebfc72" : "#404040",
      weight: id === selectedId ? 2.5 : 0.8,
      opacity: id === selectedId ? 1 : 0.6,
      fillColor: color,
      fillOpacity: id === selectedId ? 0.55 : 0.42,
    };
  };

  return (
    <div className="h-full w-full" role="application" aria-label="Mapa de riesgo por zona">
      <MapContainer
        center={[-32.9, -71.3]}
        zoom={8}
        minZoom={9}
        maxBounds={MAP_BOUNDS}
        maxBoundsViscosity={1}
        zoomControl={false}
        preferCanvas
        scrollWheelZoom
        className="h-full w-full"
      >
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution='Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics'
        />
        <ZoomControl />
        <Polygon
          positions={[WORLD_RING, REGION_HOLE]}
          pathOptions={{
            color: "transparent",
            fillColor: "#13140e",
            fillOpacity: 0.78,
            interactive: false,
          }}
        />
        <Rectangle
          bounds={REGION_BOUNDS}
          pathOptions={{
            color: "#ebfc72",
            weight: 1,
            dashArray: "6 6",
            fill: false,
            interactive: false,
          }}
        />
        <RiskSurface />
        <CellLayer data={showCells ? cells : null} colorMode={colorMode} />

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
              `${zoneLabel(zone.name, zone.display_name)} · ${zone.risk_level} · ${formatScore(zone.risk_score)} · ${zone.dominant_fuel}`,
              { sticky: true, direction: "top", className: "sigrif-tooltip" },
            );
            path.on("click", () => onSelect(zone.id));
          }}
        />
        {zones.map((zone) => {
          if (!zone.geometry) {
            return null;
          }
          const center = L.geoJSON(zone.geometry).getBounds().getCenter();
          return (
            <CircleMarker
              key={`dot-${zone.id}`}
              center={[center.lat, center.lng]}
              radius={zone.id === selectedId ? 7 : 3}
              pathOptions={{
                color: zone.id === selectedId ? "#ebfc72" : "#13140e",
                weight: zone.id === selectedId ? 2 : 0.5,
                fillColor:
                  colorMode === "fuel" ? fuelColor(zone.dominant_fuel) : riskColor(zone.risk_level),
                fillOpacity: 0.9,
              }}
              eventHandlers={{ click: () => onSelect(zone.id) }}
            />
          );
        })}
        <MapFit hasSelection={selectedId !== null} />
        <MapFocus zone={selectedZone} />
        <MapViewportTracker onChange={onViewportChange} />
      </MapContainer>
    </div>
  );
}
