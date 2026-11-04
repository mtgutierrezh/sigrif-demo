import json
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from geoalchemy2.shape import to_shape
from prometheus_client import Counter, Histogram, generate_latest
from shapely.geometry import mapping
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import Response

from ..auth import OperatorUser
from ..config import settings
from ..db import get_session, init_db
from ..events import MessagingDisabled, ensure_resources, publish_reading
from ..ia.client import IAUnavailable, predict_risk
from ..model_spec import LABELS, MODEL_VERSION
from ..models import Reading, RiskCell, Zone
from ..prescription import build_prescription
from ..schemas import (
    EvaluationOut,
    HistoryPoint,
    PrescriptionActionOut,
    ReadingOut,
    RiskFeaturesIn,
    SimulationOut,
    StatusOut,
    ZoneOut,
)

logger = logging.getLogger(__name__)
REQUESTS = Counter("sigrif_api_requests_total", "Total API requests", ["path", "method", "status"])
LATENCY = Histogram(
    "sigrif_api_request_duration_seconds",
    "Latencia de las solicitudes de la API",
    ["path", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
LATENCIES: deque[float] = deque(maxlen=500)
RNG = np.random.default_rng()


def _p95() -> float | None:
    if not LATENCIES:
        return None
    ordered = sorted(LATENCIES)
    return round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
        ensure_resources()
    except Exception:
        logger.warning("database or messaging not ready")
    yield


app = FastAPI(title="SIGRIF API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def count_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    LATENCIES.append(elapsed * 1000)
    LATENCY.labels(path, request.method).observe(elapsed)
    REQUESTS.labels(request.url.path, request.method, response.status_code).inc()
    response.headers["X-App-Color"] = settings.app_color
    response.headers["X-Model-Version"] = MODEL_VERSION
    return response


def _zone_out(session: Session, zone: Zone) -> ZoneOut:
    geojson = session.scalar(select(func.ST_AsGeoJSON(Zone.geometry)).where(Zone.id == zone.id))
    latest = session.scalars(
        select(Reading).where(Reading.zone_id == zone.id).order_by(Reading.id.desc()).limit(1)
    ).first()
    return ZoneOut(
        id=zone.id,
        name=zone.name,
        comuna=zone.comuna,
        risk_level=zone.risk_level,
        risk_score=zone.risk_score,
        updated_at=zone.updated_at,
        geometry=json.loads(geojson) if geojson else None,
        latest_reading=ReadingOut.model_validate(latest) if latest else None,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/version")
def version() -> dict[str, str]:
    return {
        "api_version": app.version,
        "model_version": MODEL_VERSION,
        "app_color": settings.app_color,
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain")


@app.get("/api/v1/status", response_model=StatusOut)
def status(
    session: Annotated[Session, Depends(get_session)],
) -> StatusOut:
    zones = session.scalar(select(func.count(Zone.id))) or 0
    last_ingest = session.scalar(select(func.max(Reading.created_at)))
    return StatusOut(
        zones=zones,
        last_ingest=last_ingest,
        model_version=MODEL_VERSION,
        p95_ms=_p95(),
        window=len(LATENCIES),
    )


@app.get("/api/v1/zones", response_model=list[ZoneOut])
def list_zones(
    session: Annotated[Session, Depends(get_session)],
) -> list[ZoneOut]:
    zones = session.scalars(select(Zone).order_by(Zone.id)).all()
    return [_zone_out(session, zone) for zone in zones]


@app.get("/api/v1/cells")
def list_cells(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    cells = session.scalars(select(RiskCell).order_by(RiskCell.h3)).all()
    features = []
    for cell in cells:
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(to_shape(cell.geometry)),
                "properties": {
                    "h3": cell.h3,
                    "dominant_fuel": cell.dominant_fuel,
                    "fuel_native": cell.fuel_native,
                    "fuel_plantation": cell.fuel_plantation,
                    "fuel_shrub": cell.fuel_shrub,
                    "fuel_grass": cell.fuel_grass,
                    "fuel_agriculture": cell.fuel_agriculture,
                    "fuel_urban": cell.fuel_urban,
                    "wui_distance_m": cell.wui_distance_m,
                    "risk_level": cell.risk_level,
                    "risk_score": cell.risk_score,
                    "updated_at": cell.updated_at.isoformat(),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/v1/zones/{zone_id}", response_model=ZoneOut)
def get_zone(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> ZoneOut:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return _zone_out(session, zone)


@app.get("/api/v1/zones/{zone_id}/history", response_model=list[HistoryPoint])
def zone_history(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
) -> list[HistoryPoint]:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    readings = session.scalars(
        select(Reading).where(Reading.zone_id == zone_id).order_by(Reading.id.desc()).limit(limit)
    ).all()
    return [
        HistoryPoint(
            risk_level=reading.risk_level,
            risk_score=reading.risk_score,
            created_at=reading.created_at,
        )
        for reading in readings
    ]


@app.post("/api/v1/simulate", response_model=SimulationOut, status_code=202)
def simulate(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    zone_id: int | None = None,
) -> SimulationOut:
    if zone_id is not None:
        zone = session.get(Zone, zone_id)
    else:
        zone = session.scalars(select(Zone).order_by(Zone.id)).first()
    if zone is None:
        if zone_id is not None:
            raise HTTPException(status_code=404, detail="Zona no encontrada")
        raise HTTPException(status_code=409, detail="No hay zonas cargadas")
    payload = {
        "zone_id": zone.id,
        "temperature": round(float(RNG.uniform(8, 38)), 2),
        "humidity": round(float(RNG.uniform(15, 85)), 2),
        "wind_speed": round(float(RNG.uniform(0, 70)), 2),
        "vegetation": round(float(RNG.uniform(0, 1)), 3),
        "historical_fires": int(RNG.integers(0, 16)),
        "slope": round(float(RNG.uniform(0, 40)), 2),
    }
    try:
        publish_reading(payload)
    except MessagingDisabled as exc:
        raise HTTPException(
            status_code=503,
            detail="La simulación asíncrona no está habilitada; usa /evaluate.",
        ) from exc
    return SimulationOut(
        zone_id=zone.id, message="Lectura sintética publicada en el evento lectura.creada"
    )


@app.post("/api/v1/zones/{zone_id}/evaluate", response_model=EvaluationOut)
def evaluate_zone(
    zone_id: int,
    payload: RiskFeaturesIn,
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> EvaluationOut:
    """Inferencia síncrona + prescripción operativa para una zona."""

    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")

    features = payload.model_dump()
    try:
        prediction = predict_risk(features)
    except IAUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está disponible. Intenta nuevamente.",
            headers={"Retry-After": "5"},
        ) from exc

    risk_level = str(prediction.get("risk_level", ""))
    if risk_level not in LABELS:
        raise HTTPException(status_code=502, detail="El servicio de IA devolvió un nivel inválido")

    risk_score = float(prediction.get("risk_score", 0.0))
    evaluated_at = datetime.now(UTC)
    session.add(
        Reading(
            zone_id=zone.id,
            **features,
            risk_level=risk_level,
            risk_score=risk_score,
            created_at=evaluated_at,
        )
    )
    zone.risk_level = risk_level
    zone.risk_score = risk_score
    session.commit()

    prescription = [
        PrescriptionActionOut(**action) for action in build_prescription(features, prediction)
    ]
    return EvaluationOut(
        zone_id=zone.id,
        risk_level=risk_level,
        risk_score=risk_score,
        probabilities=prediction.get("probabilities", {}),
        model_version=str(prediction.get("model_version", MODEL_VERSION)),
        factors=prediction.get("factors", []),
        scenario=prediction.get("scenario"),
        prescription=prescription,
        evaluated_at=evaluated_at,
    )
