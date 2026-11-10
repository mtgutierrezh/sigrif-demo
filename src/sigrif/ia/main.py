import logging
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy.orm import Session
from starlette.responses import Response

from ..config import settings
from ..db import SessionLocal, init_db
from ..events import delete_message, ensure_resources, receive_readings
from ..ml import risk_model
from ..models import Reading, Zone
from ..schemas import ModelInfoOut, PredictionOut, RiskFeaturesIn

logger = logging.getLogger(__name__)
MESSAGES = Counter(
    "sigrif_ia_messages_total", "Mensajes procesados por el servicio de IA", ["status"]
)
PREDICTIONS = Counter(
    "sigrif_ia_predictions_total", "Predicciones solicitadas por nivel de riesgo", ["risk_level"]
)
PREDICTION_LATENCY = Histogram(
    "sigrif_ia_prediction_duration_seconds",
    "Latencia del endpoint de inferencia",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2),
)


def apply_reading(session: Session, payload: dict[str, Any]) -> bool:
    zone = session.get(Zone, payload["zone_id"])
    if zone is None:
        MESSAGES.labels("missing").inc()
        return False
    historical_fires = int(payload.get("historical_fires", 0))
    result = risk_model.predict_details(
        {
            "temperature": payload["temperature"],
            "humidity": payload["humidity"],
            "wind_speed": payload["wind_speed"],
            "vegetation": payload["vegetation"],
            "historical_fires": historical_fires,
            "slope": payload["slope"],
        }
    )
    label = str(result["risk_level"])
    score = float(result["risk_score"])
    zone.risk_level = label
    zone.risk_score = score
    session.add(
        Reading(
            zone_id=zone.id,
            temperature=payload["temperature"],
            humidity=payload["humidity"],
            wind_speed=payload["wind_speed"],
            vegetation=payload["vegetation"],
            historical_fires=historical_fires,
            slope=payload["slope"],
            risk_level=label,
            risk_score=score,
        )
    )
    session.commit()
    MESSAGES.labels("processed").inc()
    return True


def consume() -> None:
    while True:
        try:
            for item in receive_readings():
                with SessionLocal() as session:
                    apply_reading(session, item["payload"])
                delete_message(item["receipt"])
        except Exception:
            logger.exception("consumer error")
            time.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
        ensure_resources()
    except Exception:
        logger.warning("database or messaging not ready")
    if settings.messaging_enabled:
        threading.Thread(target=consume, daemon=True).start()
    yield


app = FastAPI(title="SIGRIF IA", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed * 1000,
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": risk_model.model_version}


@app.post("/predict", response_model=PredictionOut, tags=["inferencia"])
def predict(payload: RiskFeaturesIn) -> PredictionOut:
    """Predicción síncrona con factores explicativos y escenario de vegetación."""

    started = time.perf_counter()
    result = risk_model.predict_details(payload.model_dump())
    PREDICTION_LATENCY.observe(time.perf_counter() - started)
    PREDICTIONS.labels(str(result["risk_level"])).inc()
    return PredictionOut(**result)


@app.get("/model", response_model=ModelInfoOut, tags=["metadatos"])
def model_info() -> ModelInfoOut:
    return ModelInfoOut(**risk_model.info())


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain")
