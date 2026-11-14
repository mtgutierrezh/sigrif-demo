import type { RiskLevel } from "../features/zones/types";

export const RISK_LEVELS: RiskLevel[] = ["Bajo", "Medio", "Alto", "Sin dato"];

export const RISK_COLORS: Record<RiskLevel, string> = {
  Bajo: "#ebfc72",
  Medio: "#bacd31",
  Alto: "#e2664a",
  "Sin dato": "#84837b",
};

export const RISK_CLASSES: Record<RiskLevel, string> = {
  Bajo: "risk-low",
  Medio: "risk-medium",
  Alto: "risk-high",
  "Sin dato": "risk-none",
};

export function riskClass(level: RiskLevel | null | undefined): string {
  return RISK_CLASSES[level ?? "Sin dato"];
}

export function riskColor(level: RiskLevel | null | undefined): string {
  return RISK_COLORS[level ?? "Sin dato"];
}

export function riskRank(level: RiskLevel | null | undefined): number {
  return { Bajo: 0, Medio: 1, Alto: 2, "Sin dato": -1 }[level ?? "Sin dato"];
}

export function riskRange(level: RiskLevel): string {
  return {
    Bajo: "Señal baja del modelo",
    Medio: "Señal media del modelo",
    Alto: "Señal alta del modelo",
    "Sin dato": "Sin lectura",
  }[level];
}
