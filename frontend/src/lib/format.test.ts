import { describe, expect, it } from "vitest";

import { formatCoordinates, formatDateTime, formatNumber, formatScore } from "./format";

describe("formatScore", () => {
  it("uses two decimals with a comma", () => {
    expect(formatScore(0.5)).toBe("0,50");
    expect(formatScore(0.1234)).toBe("0,12");
  });

  it("returns a dash when there is no score", () => {
    expect(formatScore(null)).toBe("—");
    expect(formatScore(undefined)).toBe("—");
    expect(formatScore(Number.NaN)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("formats a valid date in Santiago time", () => {
    const value = formatDateTime("2026-10-19T21:40:00Z");
    expect(value).toContain("19");
    expect(value).toContain("CLT");
  });

  it("returns Sin dato for empty or invalid values", () => {
    expect(formatDateTime(null)).toBe("Sin dato");
    expect(formatDateTime("no-es-fecha")).toBe("Sin dato");
  });
});

describe("formatNumber", () => {
  it("uses Chilean separators", () => {
    expect(formatNumber(1234.5, 1)).toBe("1.234,5");
  });

  it("returns a dash for missing values", () => {
    expect(formatNumber(null)).toBe("—");
  });
});

describe("formatCoordinates", () => {
  it("formats latitude and longitude with four decimals", () => {
    expect(formatCoordinates(-33.047, -71.612)).toBe("-33,0470 / -71,6120");
  });
});
