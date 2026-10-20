import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request
from prometheus_client import Counter, generate_latest
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from ..auth import CurrentUser, OperatorUser
from ..db import get_session, init_db
from ..events import ensure_resources, publish_reading
from ..models import Zone
from ..schemas import SimulationOut, ZoneOut

logger = logging.getLogger(__name__)
REQUESTS = Counter("sigrif_api_requests_total", "Total API requests", ["path", "method", "status"])
RNG = np.random.default_rng()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
        ensure_resources()
    except Exception:
        logger.warning("database or messaging not ready")
    yield


app = FastAPI(title="SIGRIF API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def count_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    REQUESTS.labels(request.url.path, request.method, response.status_code).inc()
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain")


@app.get("/api/v1/zones", response_model=list[ZoneOut])
def list_zones(
    session: Annotated[Session, Depends(get_session)],
    _: CurrentUser,
) -> list[Zone]:
    return list(session.scalars(select(Zone).order_by(Zone.id)))


@app.get("/api/v1/zones/{zone_id}", response_model=ZoneOut)
def get_zone(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: CurrentUser,
) -> Zone:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return zone


@app.post("/api/v1/simulate", response_model=SimulationOut, status_code=202)
def simulate(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> SimulationOut:
    zone = session.scalars(select(Zone).order_by(Zone.id)).first()
    if zone is None:
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
        zone_id=zone.id, message="Lectura sintetica publicada en el evento lectura.creada"
    )
