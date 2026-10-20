import type { MultiPolygon } from "geojson";

export type RiskLevel = "Bajo" | "Medio" | "Alto" | "Sin dato";

export interface Reading {
  temperature: number;
  humidity: number;
  wind_speed: number;
  vegetation: number;
  slope: number;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  created_at: string;
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
