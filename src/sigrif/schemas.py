from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    temperature: float
    humidity: float
    wind_speed: float
    vegetation: float
    historical_fires: int
    slope: float
    risk_level: str | None = None
    risk_score: float | None = None
    source: str = "manual"
    observed_at: datetime | None = None
    created_at: datetime


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str = ""
    comuna: str
    provincia: str = "Valparaíso"
    region: str = "Valparaíso"
    zone_type: str = "sector_municipal"
    name_source: str = "desconocida"
    name_official: bool = False
    risk_level: str
    risk_score: float
    vegetation: float = 0.3
    historical_fires: int = 0
    slope: float = 15.0
    last_source: str | None = None
    last_alert_at: datetime | None = None
    updated_at: datetime
    geometry: dict[str, Any] | None = None
    latest_reading: ReadingOut | None = None


class RiskFeaturesIn(BaseModel):
    """Variables de entrada del modelo, con los mismos rangos del dataset."""

    temperature: float = Field(ge=-10, le=50)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=150)
    vegetation: float = Field(ge=0, le=1)
    historical_fires: int = Field(ge=0, le=500)
    slope: float = Field(ge=0, le=60)


class ReadingIn(RiskFeaturesIn):
    zone_id: int


class HistoryPoint(BaseModel):
    risk_level: str | None
    risk_score: float | None
    created_at: datetime
    source: str = "manual"


class StatusOut(BaseModel):
    zones: int
    last_ingest: datetime | None
    model_version: str
    p95_ms: float | None
    window: int
    last_source: str | None = None
    freshness_minutes: float | None = None
    stale: bool | None = None
    active_alerts: int | None = None


class SimulationOut(BaseModel):
    zone_id: int
    message: str


class FactorOut(BaseModel):
    feature: str
    label: str
    value: float
    unit: str
    impact: float
    direction: str


class ScenarioOut(BaseModel):
    description: str
    risk_level: str
    risk_score: float
    delta: float


class PredictionOut(BaseModel):
    risk_level: str
    risk_score: float
    probabilities: dict[str, float]
    model_version: str
    factors: list[FactorOut]
    scenario: ScenarioOut | None = None


class PrescriptionActionOut(BaseModel):
    code: str
    title: str
    description: str
    priority: str
    horizon: str
    rationale: str


class EvaluationOut(BaseModel):
    id: int | None = None
    zone_id: int
    risk_level: str
    risk_score: float
    probabilities: dict[str, float]
    model_version: str
    factors: list[FactorOut]
    scenario: ScenarioOut | None = None
    prescription: list[PrescriptionActionOut]
    source: str = "manual"
    observed_at: datetime | None = None
    evaluated_at: datetime
    created_by: str = "local"


class EvaluationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    risk_level: str
    risk_score: float
    model_version: str
    source: str
    created_at: datetime
    prescription_count: int = 0


class ZoneAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str = ""
    comuna: str
    provincia: str = "Valparaíso"
    region: str = "Valparaíso"
    zone_type: str = "sector_municipal"
    name_source: str = "desconocida"
    name_official: bool = False
    risk_level: str
    risk_score: float
    last_source: str | None = None
    last_alert_at: datetime | None = None
    updated_at: datetime


class AlertEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    event_type: str
    detail: str | None = None
    actor: str
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    zone_name: str
    comuna: str
    evaluation_id: int | None = None
    risk_level: str | None = None
    risk_score: float | None = None
    status: str
    assigned_to: str | None = None
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    evaluation: EvaluationSummaryOut | None = None


class AlertDetailOut(AlertOut):
    events: list[AlertEventOut] = Field(default_factory=list)


class AlertUpdate(BaseModel):
    status: Literal["nueva", "en_revision", "cerrada"] | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=5000)


class AlertEventCreate(BaseModel):
    event_type: str = Field(default="comentario", max_length=30)
    detail: str = Field(min_length=1, max_length=5000)


class AlertSummaryOut(BaseModel):
    total: int
    nueva: int
    en_revision: int
    cerrada: int


class IngestionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    zones_total: int
    zones_ok: int
    zones_failed: int
    message: str | None = None
    duration_ms: int | None = None


class DriftFeatureOut(BaseModel):
    feature: str
    psi: float
    status: str
    baseline_mean: float
    current_mean: float
    samples: int


class OpsOverviewOut(BaseModel):
    zones: int
    risk_counts: dict[str, int]
    sources: dict[str, int]
    last_ingest: datetime | None = None
    last_source: str | None = None
    freshness_minutes: float | None = None
    stale: bool = False
    active_alerts: int = 0
    queue_depth: int | None = None
    model_version: str
    p95_ms: float | None = None
    drift: list[DriftFeatureOut] = Field(default_factory=list)
    last_ingestion: IngestionRunOut | None = None


class ModelInfoOut(BaseModel):
    version: str
    features: list[str]
    labels: list[str]
    trained_at: str | None
    dataset_hash: str | None
    metrics: dict[str, Any]
    feature_importance: list[dict[str, Any]]
    source: str | None


class CellOut(BaseModel):
    h3: str
    geometry: dict
    dominant_fuel: str
    fuel_native: float
    fuel_plantation: float
    fuel_shrub: float
    fuel_grass: float
    fuel_agriculture: float
    fuel_urban: float
    wui_distance_m: float
    risk_level: str
    risk_score: float
    updated_at: datetime


class OcrOut(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    text: str
    model_id: str
    latency_ms: float
    usage: dict[str, int]
    truncated: bool
    cached: bool
    image_sha256: str


class FieldReportCreate(BaseModel):
    extracted_text: str = Field(min_length=1, max_length=20000)
    confirmed_text: str = Field(min_length=1, max_length=20000)
    model_id: str = Field(max_length=80)
    source_filename: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=80)
    size_bytes: int | None = Field(default=None, ge=0, le=20 * 1024 * 1024)


class FieldReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    extracted_text: str
    confirmed_text: str
    model_id: str
    source_filename: str | None
    content_type: str | None
    size_bytes: int | None
    created_by: str
    status: str
    created_at: datetime
