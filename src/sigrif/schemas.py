from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    comuna: str
    risk_level: str
    risk_score: float
    updated_at: datetime


class ReadingIn(BaseModel):
    zone_id: int
    temperature: float = Field(ge=-10, le=50)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=150)
    vegetation: float = Field(ge=0, le=1)
    slope: float = Field(ge=0, le=60)


class SimulationOut(BaseModel):
    zone_id: int
    message: str
