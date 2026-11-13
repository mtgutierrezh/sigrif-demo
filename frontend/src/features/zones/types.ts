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
  source: string;
  observed_at: string | null;
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
  id?: number;
  zone_id: number;
  risk_level: RiskLevel;
  risk_score: number;
  probabilities: Record<string, number>;
  model_version: string;
  factors: Factor[];
  scenario: Scenario | null;
  prescription: PrescriptionAction[];
  evaluated_at: string;
  source: string;
  observed_at: string | null;
  created_by: string;
}

export interface OcrResult {
  filename: string;
  content_type: string;
  size_bytes: number;
  text: string;
  model_id: string;
  latency_ms: number;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
  truncated: boolean;
  cached: boolean;
  image_sha256: string;
}

export interface FieldReport {
  id: number;
  zone_id: number;
  extracted_text: string;
  confirmed_text: string;
  model_id: string;
  source_filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  created_by: string;
  status: string;
  created_at: string;
}

export interface Zone {
  id: number;
  name: string;
  comuna: string;
  provincia: string;
  region: string;
  zone_type: string;
  name_source: string;
  name_official: boolean;
  risk_level: RiskLevel;
  risk_score: number;
  vegetation: number;
  historical_fires: number;
  slope: number;
  last_source: string | null;
  last_alert_at: string | null;
  updated_at: string;
  geometry: MultiPolygon | null;
  latest_reading: Reading | null;
}

export interface HistoryPoint {
  risk_level: RiskLevel | null;
  risk_score: number | null;
  source: string;
  created_at: string;
}

export interface Status {
  zones: number;
  last_ingest: string | null;
  model_version: string;
  p95_ms: number | null;
  window: number;
  last_source: string | null;
  freshness_minutes: number | null;
  stale: boolean;
  active_alerts: number;
}

export interface DriftFeature {
  feature: string;
  psi: number;
  status: string;
  baseline_mean: number;
  current_mean: number;
  samples: number;
}

export interface IngestionRun {
  id: number;
  provider: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  zones_total: number;
  zones_ok: number;
  zones_failed: number;
  message: string | null;
  duration_ms: number | null;
}

export interface OpsOverview {
  zones: number;
  risk_counts: Record<string, number>;
  sources: Record<string, number>;
  last_ingest: string | null;
  last_source: string | null;
  freshness_minutes: number | null;
  stale: boolean;
  active_alerts: number;
  queue_depth: number | null;
  model_version: string;
  p95_ms: number | null;
  drift: DriftFeature[];
  last_ingestion: IngestionRun | null;
}

export interface ZoneAlert {
  id: number;
  name: string;
  comuna: string;
  risk_level: RiskLevel;
  risk_score: number;
  last_source: string | null;
  last_alert_at: string | null;
  updated_at: string;
}

export interface ModelInfo {
  version: string;
  features: string[];
  labels: string[];
  trained_at: string | null;
  dataset_hash: string | null;
  metrics: Record<string, unknown>;
  feature_importance: Array<Record<string, unknown>>;
  source: string | null;
}

export type AlertStatus = "nueva" | "en_revision" | "cerrada";

export interface EvaluationSummary {
  id: number;
  zone_id: number;
  risk_level: RiskLevel;
  risk_score: number;
  model_version: string;
  source: string;
  created_at: string;
  prescription_count: number;
}

export interface AlertEvent {
  id: number;
  alert_id: number;
  event_type: string;
  detail: string | null;
  actor: string;
  created_at: string;
}

export interface Alert {
  id: number;
  zone_id: number;
  zone_name: string;
  comuna: string;
  evaluation_id: number | null;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  status: AlertStatus;
  assigned_to: string | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  evaluation: EvaluationSummary | null;
}

export interface AlertDetail extends Alert {
  events: AlertEvent[];
}

export interface AlertSummary {
  total: number;
  nueva: number;
  en_revision: number;
  cerrada: number;
}

export interface AlertUpdatePayload {
  status?: AlertStatus;
  assigned_to?: string;
  comment?: string;
}

export interface AlertEventPayload {
  event_type: string;
  detail: string;
}
