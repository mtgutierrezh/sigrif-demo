import { describe, expect, it } from "vitest";

import type { MultiPolygon } from "geojson";

import type { Zone } from "../features/zones/types";
import { geometryCentroid, haversineKm, nearestZoneByCentroid } from "./geo";

function square(minLon: number, minLat: number, size: number): MultiPolygon {
  return {
    type: "MultiPolygon",
    coordinates: [
      [
        [
          [minLon, minLat],
          [minLon + size, minLat],
          [minLon + size, minLat + size],
          [minLon, minLat + size],
          [minLon, minLat],
        ],
      ],
    ],
  };
}

function zone(id: number, geometry: MultiPolygon): Zone {
  return { id, name: `Zona ${id}`, geometry } as Zone;
}

describe("geometryCentroid", () => {
  it("calcula el centroide de área de un polígono", () => {
    expect(geometryCentroid(square(0, 0, 2))).toEqual([1, 1]);
  });

  it("devuelve null sin geometría", () => {
    expect(geometryCentroid(null)).toBeNull();
  });
});

describe("nearestZoneByCentroid", () => {
  it("elige la zona cuyo centroide está más cerca", () => {
    const nearest = nearestZoneByCentroid(
      [zone(1, square(0, 0, 2)), zone(2, square(10, 10, 2))],
      1.1,
      1.1,
    );

    expect(nearest?.zone.id).toBe(1);
    expect(nearest?.distanceKm).toBeLessThan(20);
  });

  it("devuelve null si ninguna zona tiene geometría", () => {
    expect(nearestZoneByCentroid([], -33, -71)).toBeNull();
  });
});

describe("haversineKm", () => {
  it("calcula una distancia razonable entre Valparaíso y Santiago", () => {
    const distance = haversineKm(-33.05, -71.61, -33.45, -70.67);

    expect(distance).toBeGreaterThan(80);
    expect(distance).toBeLessThan(120);
  });
});
