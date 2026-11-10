from datetime import datetime
from typing import Any

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
    created_at: datetime


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    comuna: str
    risk_level: str
    risk_score: float
    updated_at: datetime
    geometry: dict[str, Any] | None = None
    latest_reading: ReadingOut | None = None


class RiskFeaturesIn(BaseModel):
    """Variables de entrada del modelo, con los mismos rangos del dataset."""

    temperature: float = Field(ge=-10, le=50)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=150)
    vegetation: float = Field(ge=0, le=1)
    historical_fires: int = Field(ge=0, le=30)
    slope: float = Field(ge=0, le=60)


class ReadingIn(RiskFeaturesIn):
    zone_id: int


class HistoryPoint(BaseModel):
    risk_level: str | None
    risk_score: float | None
    created_at: datetime


class StatusOut(BaseModel):
    zones: int
    last_ingest: datetime | None
    model_version: str
    p95_ms: float | None
    window: int


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
    zone_id: int
    risk_level: str
    risk_score: float
    probabilities: dict[str, float]
    model_version: str
    factors: list[FactorOut]
    scenario: ScenarioOut | None = None
    prescription: list[PrescriptionActionOut]
    evaluated_at: datetime


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
