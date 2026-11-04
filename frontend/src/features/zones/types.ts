import type { MultiPolygon } from "geojson";

export type RiskLevel = "Bajo" | "Medio" | "Alto" | "Sin dato";

export interface Reading {
  temperature: number;
  humidity: number;
  wind_speed: number;
  vegetation: number;
  historical_fires: number;
  slope: number;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  created_at: string;
}

export interface RiskFeatures {
  temperature: number;
  humidity: number;
  wind_speed: number;
  vegetation: number;
  historical_fires: number;
  slope: number;
}

export interface Factor {
  feature: string;
  label: string;
  value: number;
  unit: string;
  impact: number;
  direction: string;
}

export interface Scenario {
  description: string;
  risk_level: RiskLevel;
  risk_score: number;
  delta: number;
}

export interface PrescriptionAction {
  code: string;
  title: string;
  description: string;
  priority: string;
  horizon: string;
  rationale: string;
}

export interface Evaluation {
  zone_id: number;
  risk_level: RiskLevel;
  risk_score: number;
  probabilities: Record<string, number>;
  model_version: string;
  factors: Factor[];
  scenario: Scenario | null;
  prescription: PrescriptionAction[];
  evaluated_at: string;
}

export interface Zone {
  id: number;
  name: string;
  comuna: string;
  risk_level: RiskLevel;
  risk_score: number;
  updated_at: string;
  geometry: MultiPolygon | null;
  latest_reading: Reading | null;
}

export interface HistoryPoint {
  risk_level: RiskLevel | null;
  risk_score: number | null;
  created_at: string;
}

export interface Status {
  zones: number;
  last_ingest: string | null;
  model_version: string;
  p95_ms: number | null;
  window: number;
}
