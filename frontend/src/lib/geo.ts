import type { Feature, FeatureCollection, MultiPolygon, Position } from "geojson";

import type { Zone } from "../features/zones/types";

export type ZoneFeature = Feature<MultiPolygon, { id: number; name: string; risk: string }>;

export interface NearestZone {
  zone: Zone;
  distanceKm: number;
}

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

function ringCentroid(ring: Position[]): { area: number; x: number; y: number } {
  let area = 0;
  let weightedX = 0;
  let weightedY = 0;
  for (let index = 0; index < ring.length; index += 1) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[(index + 1) % ring.length];
    const cross = x1 * y2 - x2 * y1;
    area += cross;
    weightedX += (x1 + x2) * cross;
    weightedY += (y1 + y2) * cross;
  }
  area /= 2;
  if (Math.abs(area) < 1e-12) {
    return { area: 0, x: 0, y: 0 };
  }
  return { area, x: weightedX / (6 * area), y: weightedY / (6 * area) };
}

/** Centroide de área del MultiPolygon, en orden [longitud, latitud]. */
export function geometryCentroid(
  geometry: MultiPolygon | null | undefined,
): [number, number] | null {
  if (!geometry || geometry.type !== "MultiPolygon") {
    return null;
  }
  let totalArea = 0;
  let weightedX = 0;
  let weightedY = 0;
  let fallbackX = 0;
  let fallbackY = 0;
  let points = 0;

  for (const polygon of geometry.coordinates) {
    for (const [ringIndex, ring] of polygon.entries()) {
      for (const [x, y] of ring) {
        fallbackX += x;
        fallbackY += y;
        points += 1;
      }
      const centroid = ringCentroid(ring);
      const area = ringIndex === 0 ? Math.abs(centroid.area) : -Math.abs(centroid.area);
      totalArea += area;
      weightedX += centroid.x * area;
      weightedY += centroid.y * area;
    }
  }

  if (Math.abs(totalArea) < 1e-12) {
    return points > 0 ? [fallbackX / points, fallbackY / points] : null;
  }
  return [weightedX / totalArea, weightedY / totalArea];
}

export function haversineKm(
  latitude: number,
  longitude: number,
  otherLatitude: number,
  otherLongitude: number,
): number {
  const radius = 6371;
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const deltaLat = toRadians(otherLatitude - latitude);
  const deltaLon = toRadians(otherLongitude - longitude);
  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(toRadians(latitude)) *
      Math.cos(toRadians(otherLatitude)) *
      Math.sin(deltaLon / 2) ** 2;
  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function nearestZoneByCentroid(
  zones: Zone[],
  latitude: number,
  longitude: number,
): NearestZone | null {
  let nearest: NearestZone | null = null;
  for (const zone of zones) {
    const centroid = geometryCentroid(zone.geometry);
    if (!centroid) {
      continue;
    }
    const [zoneLongitude, zoneLatitude] = centroid;
    const distanceKm = haversineKm(latitude, longitude, zoneLatitude, zoneLongitude);
    if (nearest === null || distanceKm < nearest.distanceKm) {
      nearest = { zone, distanceKm };
    }
  }
  return nearest;
}
