import json
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
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

from ..auth import CurrentUser, OperatorUser
from ..config import settings
from ..db import get_session, init_db
from ..events import ensure_resources, publish_reading
from ..models import Reading, RiskCell, Zone
from ..schemas import HistoryPoint, ReadingOut, SimulationOut, StatusOut, ZoneOut

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


app = FastAPI(title="SIGRIF API", version="0.1.0", lifespan=lifespan)
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


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain")


@app.get("/api/v1/status", response_model=StatusOut)
def status(
    session: Annotated[Session, Depends(get_session)],
    _: CurrentUser,
) -> StatusOut:
    zones = session.scalar(select(func.count(Zone.id))) or 0
    last_ingest = session.scalar(select(func.max(Reading.created_at)))
    return StatusOut(
        zones=zones,
        last_ingest=last_ingest,
        model_version="random-forest-0.1",
        p95_ms=_p95(),
        window=len(LATENCIES),
    )


@app.get("/api/v1/zones", response_model=list[ZoneOut])
def list_zones(
    session: Annotated[Session, Depends(get_session)],
    _: CurrentUser,
) -> list[ZoneOut]:
    zones = session.scalars(select(Zone).order_by(Zone.id)).all()
    return [_zone_out(session, zone) for zone in zones]


@app.get("/api/v1/cells")
def list_cells(
    session: Annotated[Session, Depends(get_session)],
    _: CurrentUser,
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
    _: CurrentUser,
) -> ZoneOut:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return _zone_out(session, zone)


@app.get("/api/v1/zones/{zone_id}/history", response_model=list[HistoryPoint])
def zone_history(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: CurrentUser,
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
        "slope": round(float(RNG.uniform(0, 40)), 2),
    }
    publish_reading(payload)
    return SimulationOut(
        zone_id=zone.id, message="Lectura sintética publicada en el evento lectura.creada"
    )
