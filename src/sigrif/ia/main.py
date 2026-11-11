import logging
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from ..config import settings
from ..db import SessionLocal, init_db
from ..evaluation import evaluate_and_store
from ..events import delete_message, ensure_resources, receive_readings
from ..ml import risk_model
from ..models import Zone
from ..schemas import ModelInfoOut, OcrOut, PredictionOut, RiskFeaturesIn
from .bedrock_ocr import (
    ALLOWED_CONTENT_TYPES,
    OcrUnavailable,
    detect_content_type,
    extract_text,
)

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
OCR_REQUESTS = Counter("sigrif_ia_ocr_requests_total", "Solicitudes de OCR procesadas", ["status"])
OCR_LATENCY = Histogram(
    "sigrif_ia_ocr_duration_seconds",
    "Latencia del OCR con Bedrock",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30),
)


def apply_reading(session: Session, payload: dict[str, Any]) -> bool:
    zone = session.get(Zone, payload["zone_id"])
    if zone is None:
        MESSAGES.labels("missing").inc()
        return False
    features = {
        "temperature": float(payload["temperature"]),
        "humidity": float(payload["humidity"]),
        "wind_speed": float(payload["wind_speed"]),
        "vegetation": float(payload["vegetation"]),
        "historical_fires": int(payload.get("historical_fires", 0)),
        "slope": float(payload["slope"]),
    }
    evaluate_and_store(
        session,
        zone,
        features,
        source=str(payload.get("source", "manual")),
        observed_at=payload.get("observed_at"),
        created_by="ingest",
    )
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
    return {
        "status": "ok",
        "model_version": risk_model.model_version,
        "ocr": "enabled" if settings.bedrock_enabled else "disabled",
    }


@app.post("/predict", response_model=PredictionOut, tags=["inferencia"])
def predict(payload: RiskFeaturesIn) -> PredictionOut:
    """Predicción síncrona con factores explicativos y escenario de vegetación."""

    started = time.perf_counter()
    result = risk_model.predict_details(payload.model_dump())
    PREDICTION_LATENCY.observe(time.perf_counter() - started)
    PREDICTIONS.labels(str(result["risk_level"])).inc()
    return PredictionOut(**result)


@app.post("/ocr", response_model=OcrOut, tags=["ocr"])
async def ocr(file: Annotated[UploadFile, File()]) -> OcrOut:
    """Extrae texto de una ficha de terreno con Bedrock Nova Lite."""

    if not settings.bedrock_enabled:
        raise HTTPException(status_code=503, detail="El OCR con Bedrock no está habilitado")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Formato no permitido. Usa JPEG, PNG o WebP.",
        )

    image_bytes = await file.read(settings.ocr_max_bytes + 1)
    if len(image_bytes) > settings.ocr_max_bytes:
        raise HTTPException(status_code=413, detail="La imagen supera el tamaño máximo de 5 MB")
    if detect_content_type(image_bytes) != content_type:
        raise HTTPException(
            status_code=415,
            detail="El contenido no coincide con el tipo declarado",
        )

    started = time.perf_counter()
    try:
        result = await run_in_threadpool(extract_text, image_bytes, content_type)
    except OcrUnavailable as exc:
        OCR_REQUESTS.labels("unavailable").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    OCR_LATENCY.observe(time.perf_counter() - started)
    OCR_REQUESTS.labels("ok").inc()
    return OcrOut(
        filename=file.filename or "ficha",
        content_type=content_type,
        size_bytes=len(image_bytes),
        **result,
    )


@app.get("/model", response_model=ModelInfoOut, tags=["metadatos"])
def model_info() -> ModelInfoOut:
    return ModelInfoOut(**risk_model.info())


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain")
