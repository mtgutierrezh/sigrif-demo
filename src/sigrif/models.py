from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    comuna: Mapped[str] = mapped_column(String(80))
    provincia: Mapped[str] = mapped_column(
        String(80), default="Valparaíso", server_default="Valparaíso"
    )
    region: Mapped[str] = mapped_column(
        String(80), default="Valparaíso", server_default="Valparaíso"
    )
    zone_type: Mapped[str] = mapped_column(
        String(30), default="sector_municipal", server_default="sector_municipal"
    )
    name_source: Mapped[str] = mapped_column(
        String(120), default="desconocida", server_default="desconocida"
    )
    name_official: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    geometry: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    risk_level: Mapped[str] = mapped_column(String(10), default="Bajo")

    @property
    def display_name(self) -> str:
        return self.name

    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    vegetation: Mapped[float] = mapped_column(Float, default=0.3, server_default="0.3")
    historical_fires: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    slope: Mapped[float] = mapped_column(Float, default=15.0, server_default="15")
    fuel_native: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    fuel_plantation: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    fuel_shrub: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    fuel_grass: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    fuel_agriculture: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    fuel_urban: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    dominant_fuel: Mapped[str] = mapped_column(
        String(30), default="Sin dato", server_default="Sin dato"
    )
    last_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    wind_speed: Mapped[float] = mapped_column(Float)
    vegetation: Mapped[float] = mapped_column(Float)
    historical_fires: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    slope: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zone: Mapped[Zone] = relationship()
    __table_args__ = (
        Index(
            "ix_readings_zone_observed",
            "zone_id",
            "observed_at",
            unique=True,
            postgresql_where=text("observed_at IS NOT NULL"),
        ),
    )


class FieldReport(Base):
    __tablename__ = "field_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    extracted_text: Mapped[str] = mapped_column(Text)
    confirmed_text: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(String(80))
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="local")
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zone: Mapped[Zone] = relationship()


class RiskCell(Base):
    __tablename__ = "risk_cells"

    h3: Mapped[str] = mapped_column(String(20), primary_key=True)
    geometry: Mapped[Any] = mapped_column(Geometry("POLYGON", srid=4326))
    zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    comuna: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    provincia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    zone_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dominant_fuel: Mapped[str] = mapped_column(String(20))
    fuel_native: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_plantation: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_shrub: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_grass: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_agriculture: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_urban: Mapped[float] = mapped_column(Float, default=0.0)
    slope: Mapped[float] = mapped_column(Float, default=15.0, server_default="15")
    historical_fires: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    wui_distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(10), default="Bajo")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    fire_probability: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    fire_risk_level: Mapped[str] = mapped_column(String(10), default="Bajo", server_default="Bajo")
    fire_model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fire_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    reading_id: Mapped[int | None] = mapped_column(
        ForeignKey("readings.id", ondelete="SET NULL"), nullable=True
    )
    risk_level: Mapped[str] = mapped_column(String(10))
    risk_score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(40))
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    probabilities: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    scenario: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    prescription: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zone: Mapped[Zone] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    evaluation_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="nueva", server_default="nueva", nullable=False
    )
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zone: Mapped[Zone] = relationship()
    evaluation: Mapped[Evaluation | None] = relationship()
    events: Mapped[list["AlertEvent"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
        order_by="AlertEvent.id",
    )
    __table_args__ = (
        Index("ix_alerts_zone_status", "zone_id", "status"),
        Index("ix_alerts_created_at", "created_at"),
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(120), default="sistema")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    alert: Mapped[Alert] = relationship(back_populates="events")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zones_total: Mapped[int] = mapped_column(Integer, default=0)
    zones_ok: Mapped[int] = mapped_column(Integer, default=0)
    zones_failed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
