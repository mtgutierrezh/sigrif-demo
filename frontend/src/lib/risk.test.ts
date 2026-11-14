import { describe, expect, it } from "vitest";

import { RISK_LEVELS, riskClass, riskColor, riskRank, riskRange } from "./risk";

describe("risk tokens", () => {
  it("defines the four levels in order", () => {
    expect(RISK_LEVELS).toEqual(["Bajo", "Medio", "Alto", "Sin dato"]);
  });

  it("maps levels to classes", () => {
    expect(riskClass("Bajo")).toBe("risk-low");
    expect(riskClass("Medio")).toBe("risk-medium");
    expect(riskClass("Alto")).toBe("risk-high");
    expect(riskClass("Sin dato")).toBe("risk-none");
  });

  it("maps levels to colors", () => {
    expect(riskColor("Bajo")).toBe("#ebfc72");
    expect(riskColor("Alto")).toBe("#e2664a");
  });

  it("orders levels by severity", () => {
    expect(riskRank("Bajo")).toBe(0);
    expect(riskRank("Medio")).toBe(1);
    expect(riskRank("Alto")).toBe(2);
    expect(riskRank("Sin dato")).toBe(-1);
  });

  it("exposes the score guidance", () => {
    expect(riskRange("Bajo")).toBe("Señal baja del modelo");
    expect(riskRange("Alto")).toBe("Señal alta del modelo");
  });
});
