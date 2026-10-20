from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    temperature: float
    humidity: float
    wind_speed: float
    vegetation: float
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


class ReadingIn(BaseModel):
    zone_id: int
    temperature: float = Field(ge=-10, le=50)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=150)
    vegetation: float = Field(ge=0, le=1)
    slope: float = Field(ge=0, le=60)


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
