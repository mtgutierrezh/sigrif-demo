import json
import logging
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from geoalchemy2.shape import to_shape
from prometheus_client import Counter, Histogram, generate_latest
from shapely.geometry import mapping
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import Response

from ..alerts import ALERT_STATUSES, add_event, update_alert
from ..auth import OperatorUser
from ..config import settings
from ..db import get_session, init_db
from ..evaluation import store_evaluation
from ..events import MessagingDisabled, ensure_resources, publish_reading, queue_depth
from ..ia.bedrock_ocr import ALLOWED_CONTENT_TYPES, detect_content_type
from ..ia.client import IAUnavailable, model_info, ocr_image, predict_risk
from ..ingest.service import run_ingestion
from ..model_spec import LABELS, MODEL_VERSION
from ..models import (
    Alert,
    AlertEvent,
    Evaluation,
    FieldReport,
    IngestionRun,
    Reading,
    RiskCell,
    Zone,
)
from ..monitoring import (
    data_timestamps,
    drift_report,
    freshness_minutes,
    refresh_metrics,
    risk_counts,
)
from ..prescription import build_prescription
from ..reports import report_filename, zone_csv_bytes, zone_pdf_bytes, zones_summary_csv_bytes
from ..schemas import (
    AlertDetailOut,
    AlertEventCreate,
    AlertEventOut,
    AlertOut,
    AlertSummaryOut,
    AlertUpdate,
    DriftFeatureOut,
    EvaluationOut,
    EvaluationSummaryOut,
    FactorOut,
    FieldReportCreate,
    FieldReportOut,
    HistoryPoint,
    IngestionRunOut,
    ModelInfoOut,
    OcrOut,
    OpsOverviewOut,
    PrescriptionActionOut,
    ReadingOut,
    RiskFeaturesIn,
    ScenarioOut,
    SimulationOut,
    StatusOut,
    ZoneAlertOut,
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
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def count_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    LATENCIES.append(elapsed * 1000)
    LATENCY.labels(path, request.method).observe(elapsed)
    REQUESTS.labels(request.url.path, request.method, response.status_code).inc()
    response.headers["X-Request-ID"] = request_id
    response.headers["X-App-Color"] = settings.app_color
    response.headers["X-Model-Version"] = MODEL_VERSION
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed * 1000,
    )
    return response


def _zone_out(session: Session, zone: Zone) -> ZoneOut:
    geojson = session.scalar(select(func.ST_AsGeoJSON(Zone.geometry)).where(Zone.id == zone.id))
    latest = session.scalars(
        select(Reading).where(Reading.zone_id == zone.id).order_by(Reading.id.desc()).limit(1)
    ).first()
    return ZoneOut(
        id=zone.id,
        name=zone.name,
        display_name=zone.display_name,
        comuna=zone.comuna,
        provincia=zone.provincia,
        region=zone.region,
        zone_type=zone.zone_type,
        name_source=zone.name_source,
        name_official=zone.name_official,
        risk_level=zone.risk_level,
        risk_score=zone.risk_score,
        vegetation=zone.vegetation,
        historical_fires=zone.historical_fires,
        slope=zone.slope,
        fuel_native=zone.fuel_native,
        fuel_plantation=zone.fuel_plantation,
        fuel_shrub=zone.fuel_shrub,
        fuel_grass=zone.fuel_grass,
        fuel_agriculture=zone.fuel_agriculture,
        fuel_urban=zone.fuel_urban,
        dominant_fuel=zone.dominant_fuel,
        last_source=zone.last_source,
        last_alert_at=zone.last_alert_at,
        updated_at=zone.updated_at,
        geometry=json.loads(geojson) if geojson else None,
        latest_reading=ReadingOut.model_validate(latest) if latest else None,
    )


def _evaluation_summary(evaluation: Evaluation) -> EvaluationSummaryOut:
    return EvaluationSummaryOut(
        id=evaluation.id,
        zone_id=evaluation.zone_id,
        risk_level=evaluation.risk_level,
        risk_score=evaluation.risk_score,
        model_version=evaluation.model_version,
        source=evaluation.source,
        created_at=evaluation.created_at,
        prescription_count=len(evaluation.prescription or []),
    )


def _latest_evaluation(session: Session, zone_id: int) -> Evaluation | None:
    return session.scalars(
        select(Evaluation)
        .where(Evaluation.zone_id == zone_id)
        .order_by(Evaluation.id.desc())
        .limit(1)
    ).first()


def _alert_out(session: Session, alert: Alert) -> AlertOut:
    zone = session.get(Zone, alert.zone_id)
    evaluation = (
        session.get(Evaluation, alert.evaluation_id) if alert.evaluation_id is not None else None
    )
    return AlertOut(
        id=alert.id,
        zone_id=alert.zone_id,
        zone_name=zone.name if zone is not None else f"Zona {alert.zone_id}",
        comuna=zone.comuna if zone is not None else "",
        evaluation_id=alert.evaluation_id,
        risk_level=evaluation.risk_level if evaluation else (zone.risk_level if zone else None),
        risk_score=evaluation.risk_score if evaluation else (zone.risk_score if zone else None),
        status=alert.status,
        assigned_to=alert.assigned_to,
        comment=alert.comment,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        closed_at=alert.closed_at,
        evaluation=_evaluation_summary(evaluation) if evaluation else None,
    )


def _alert_detail(session: Session, alert: Alert) -> AlertDetailOut:
    base = _alert_out(session, alert)
    events = session.scalars(
        select(AlertEvent)
        .where(AlertEvent.alert_id == alert.id)
        .order_by(AlertEvent.created_at, AlertEvent.id)
    ).all()
    return AlertDetailOut(
        **base.model_dump(),
        events=[AlertEventOut.model_validate(event) for event in events],
    )


def _report_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


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
def metrics(session: Annotated[Session, Depends(get_session)]) -> Response:
    try:
        refresh_metrics(session)
    except Exception:
        logger.exception("no se pudieron refrescar las métricas operativas")
    return Response(generate_latest(), media_type="text/plain")


@app.get("/api/v1/status", response_model=StatusOut)
def status(
    session: Annotated[Session, Depends(get_session)],
) -> StatusOut:
    zones = session.scalar(select(func.count(Zone.id))) or 0
    last_ingest, last_source = data_timestamps(session)
    freshness = freshness_minutes(last_ingest)
    active_alerts = (
        session.scalar(select(func.count(Zone.id)).where(Zone.risk_level == "Alto")) or 0
    )
    return StatusOut(
        zones=zones,
        last_ingest=last_ingest,
        model_version=MODEL_VERSION,
        p95_ms=_p95(),
        window=len(LATENCIES),
        last_source=last_source,
        freshness_minutes=freshness,
        stale=freshness is None or freshness > 45,
        active_alerts=int(active_alerts),
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
            source=reading.source,
        )
        for reading in readings
    ]


@app.get("/api/v1/model", response_model=ModelInfoOut)
def get_model_info(
    request: Request,
    _: OperatorUser,
) -> ModelInfoOut:
    """Model card en vivo, solo para operadores."""

    try:
        info = model_info(request_id=getattr(request.state, "request_id", None))
    except IAUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está disponible.",
            headers={"Retry-After": "5"},
        ) from exc
    return ModelInfoOut(**info)


@app.get("/api/v1/evaluations", response_model=list[EvaluationSummaryOut])
def list_evaluations(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    zone_id: int | None = None,
    risk_level: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EvaluationSummaryOut]:
    stmt = select(Evaluation).order_by(Evaluation.id.desc()).limit(limit)
    if zone_id is not None:
        stmt = stmt.where(Evaluation.zone_id == zone_id)
    if risk_level is not None:
        if risk_level not in LABELS:
            raise HTTPException(status_code=422, detail="Nivel de riesgo inválido")
        stmt = stmt.where(Evaluation.risk_level == risk_level)
    evaluations = session.scalars(stmt).all()
    return [_evaluation_summary(evaluation) for evaluation in evaluations]


@app.get(
    "/api/v1/zones/{zone_id}/evaluations",
    response_model=list[EvaluationSummaryOut],
)
def zone_evaluations(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[EvaluationSummaryOut]:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    evaluations = session.scalars(
        select(Evaluation)
        .where(Evaluation.zone_id == zone_id)
        .order_by(Evaluation.id.desc())
        .limit(limit)
    ).all()
    return [_evaluation_summary(evaluation) for evaluation in evaluations]


@app.get("/api/v1/ops/overview", response_model=OpsOverviewOut)
def ops_overview(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> OpsOverviewOut:
    counts = risk_counts(session)
    sources = {
        str(source): int(count)
        for source, count in session.execute(
            select(Reading.source, func.count(Reading.id)).group_by(Reading.source)
        )
    }
    last_ingest, last_source = data_timestamps(session)
    freshness = freshness_minutes(last_ingest)
    last_run = session.scalars(
        select(IngestionRun).order_by(IngestionRun.id.desc()).limit(1)
    ).first()
    try:
        depth = queue_depth()
    except Exception:
        depth = None
    return OpsOverviewOut(
        zones=sum(counts.values()),
        risk_counts=counts,
        sources=sources,
        last_ingest=last_ingest,
        last_source=last_source,
        freshness_minutes=freshness,
        stale=freshness is None or freshness > 45,
        active_alerts=counts.get("Alto", 0),
        queue_depth=depth,
        model_version=MODEL_VERSION,
        p95_ms=_p95(),
        drift=[DriftFeatureOut(**item) for item in drift_report(session)],
        last_ingestion=IngestionRunOut.model_validate(last_run) if last_run else None,
    )


@app.get("/api/v1/ops/alerts", response_model=list[ZoneAlertOut])
def ops_alerts(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ZoneAlertOut]:
    zones = session.scalars(
        select(Zone).where(Zone.risk_level == "Alto").order_by(Zone.updated_at.desc()).limit(limit)
    ).all()
    return [ZoneAlertOut.model_validate(zone) for zone in zones]


@app.get("/api/v1/alerts/summary", response_model=AlertSummaryOut)
def alerts_summary(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> AlertSummaryOut:
    rows = session.execute(select(Alert.status, func.count(Alert.id)).group_by(Alert.status)).all()
    counts = {str(status): int(count) for status, count in rows}
    return AlertSummaryOut(
        total=sum(counts.values()),
        nueva=counts.get("nueva", 0),
        en_revision=counts.get("en_revision", 0),
        cerrada=counts.get("cerrada", 0),
    )


@app.get("/api/v1/alerts", response_model=list[AlertOut])
def list_alerts(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    status: str | None = None,
    zone_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AlertOut]:
    if status is not None and status not in ALERT_STATUSES:
        raise HTTPException(status_code=422, detail="Estado de alerta inválido")
    stmt = select(Alert)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    if zone_id is not None:
        stmt = stmt.where(Alert.zone_id == zone_id)
    stmt = stmt.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
    alerts = session.scalars(stmt).all()
    return [_alert_out(session, alert) for alert in alerts]


@app.get("/api/v1/alerts/{alert_id}", response_model=AlertDetailOut)
def get_alert(
    alert_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> AlertDetailOut:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return _alert_detail(session, alert)


@app.patch("/api/v1/alerts/{alert_id}", response_model=AlertDetailOut)
def patch_alert(
    alert_id: int,
    payload: AlertUpdate,
    session: Annotated[Session, Depends(get_session)],
    user: OperatorUser,
) -> AlertDetailOut:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    try:
        update_alert(
            session,
            alert,
            status=payload.status,
            assigned_to=payload.assigned_to,
            comment=payload.comment,
            actor=str(user.get("sub", "local")),
        )
        session.commit()
        session.refresh(alert)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _alert_detail(session, alert)


@app.post(
    "/api/v1/alerts/{alert_id}/events",
    response_model=AlertEventOut,
    status_code=201,
)
def create_alert_event(
    alert_id: int,
    payload: AlertEventCreate,
    session: Annotated[Session, Depends(get_session)],
    user: OperatorUser,
) -> AlertEventOut:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    event = add_event(
        session,
        alert,
        payload.event_type,
        detail=payload.detail,
        actor=str(user.get("sub", "local")),
    )
    session.commit()
    session.refresh(event)
    return AlertEventOut.model_validate(event)


@app.get("/api/v1/zones/{zone_id}/report.csv")
def zone_report_csv(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> Response:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    evaluation = _latest_evaluation(session, zone_id)
    if evaluation is None:
        raise HTTPException(
            status_code=404,
            detail="La zona no tiene evaluaciones registradas; genera una evaluación primero.",
        )
    reading = (
        session.get(Reading, evaluation.reading_id) if evaluation.reading_id is not None else None
    )
    content = zone_csv_bytes(zone, evaluation, reading, evaluation.prescription or [])
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers=_report_headers(report_filename(zone, "csv")),
    )


@app.get("/api/v1/zones/{zone_id}/report.pdf")
def zone_report_pdf(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> Response:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    evaluation = _latest_evaluation(session, zone_id)
    if evaluation is None:
        raise HTTPException(
            status_code=404,
            detail="La zona no tiene evaluaciones registradas; genera una evaluación primero.",
        )
    reading = (
        session.get(Reading, evaluation.reading_id) if evaluation.reading_id is not None else None
    )
    content = zone_pdf_bytes(zone, evaluation, reading, evaluation.prescription or [])
    return Response(
        content=content,
        media_type="application/pdf",
        headers=_report_headers(report_filename(zone, "pdf")),
    )


@app.get("/api/v1/reports/zones.csv")
def zones_report_csv(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> Response:
    zones = session.scalars(select(Zone).order_by(Zone.id)).all()
    if not zones:
        raise HTTPException(status_code=404, detail="No hay zonas cargadas")
    rows = [(zone, _latest_evaluation(session, zone.id)) for zone in zones]
    if not any(evaluation is not None for _, evaluation in rows):
        raise HTTPException(
            status_code=404,
            detail="No hay evaluaciones registradas; genera al menos una evaluación primero.",
        )
    return Response(
        content=zones_summary_csv_bytes(rows),
        media_type="text/csv; charset=utf-8",
        headers=_report_headers(report_filename(None, "csv")),
    )


@app.get("/api/v1/ops/ingestion", response_model=list[IngestionRunOut])
def ops_ingestion(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[IngestionRunOut]:
    runs = session.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(limit)).all()
    return [IngestionRunOut.model_validate(run) for run in runs]


@app.get("/api/v1/ops/drift", response_model=list[DriftFeatureOut])
def ops_drift(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
) -> list[DriftFeatureOut]:
    return [DriftFeatureOut(**item) for item in drift_report(session)]


@app.post("/api/v1/ops/ingest", response_model=IngestionRunOut)
def ops_ingest(
    session: Annotated[Session, Depends(get_session)],
    _: OperatorUser,
    provider: str | None = Query(default=None, pattern="^(auto|dmc|open_meteo|synthetic)$"),
) -> IngestionRunOut:
    """Dispara una ingesta manual desde el panel operativo."""

    try:
        run = run_ingestion(session, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return IngestionRunOut.model_validate(run)


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
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: OperatorUser,
) -> EvaluationOut:
    """Inferencia síncrona, prescripción y registro auditable de la evaluación."""

    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")

    features = payload.model_dump()
    try:
        prediction = predict_risk(
            features,
            request_id=getattr(request.state, "request_id", None),
        )
    except IAUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está disponible. Intenta nuevamente.",
            headers={"Retry-After": "5"},
        ) from exc

    risk_level = str(prediction.get("risk_level", ""))
    if risk_level not in LABELS:
        raise HTTPException(status_code=502, detail="El servicio de IA devolvió un nivel inválido")

    actions = [
        PrescriptionActionOut(**action) for action in build_prescription(features, prediction)
    ]
    evaluation = store_evaluation(
        session,
        zone,
        features,
        prediction,
        source="manual",
        request_id=getattr(request.state, "request_id", None),
        created_by=str(user.get("sub", "local")),
        prescription_actions=[action.model_dump() for action in actions],
    )
    return EvaluationOut(
        id=evaluation.id,
        zone_id=evaluation.zone_id,
        risk_level=evaluation.risk_level,
        risk_score=evaluation.risk_score,
        probabilities=evaluation.probabilities,
        model_version=evaluation.model_version,
        factors=[FactorOut(**item) for item in evaluation.factors],
        scenario=ScenarioOut(**evaluation.scenario) if evaluation.scenario else None,
        prescription=actions,
        source=evaluation.source,
        observed_at=None,
        evaluated_at=evaluation.created_at,
        created_by=evaluation.created_by,
    )


@app.post("/api/v1/field-reports/ocr", response_model=OcrOut)
async def ocr_field_report(
    request: Request,
    _: OperatorUser,
    file: Annotated[UploadFile, File()],
) -> OcrOut:
    """Extrae texto de una ficha; la imagen no se persiste en esta etapa."""

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Formato no permitido. Usa JPEG, PNG o WebP.")

    image_bytes = await file.read(settings.ocr_max_bytes + 1)
    if len(image_bytes) > settings.ocr_max_bytes:
        raise HTTPException(status_code=413, detail="La imagen supera el tamaño máximo de 5 MB")
    if detect_content_type(image_bytes) != content_type:
        raise HTTPException(
            status_code=415,
            detail="El contenido no coincide con el tipo declarado",
        )

    try:
        result = ocr_image(
            image_bytes,
            file.filename or "ficha",
            content_type,
            request_id=getattr(request.state, "request_id", None),
        )
    except IAUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="El servicio de OCR no está disponible. Intenta nuevamente.",
            headers={"Retry-After": "5"},
        ) from exc

    return OcrOut(**result)


@app.post(
    "/api/v1/zones/{zone_id}/field-reports",
    response_model=FieldReportOut,
    status_code=201,
)
def create_field_report(
    zone_id: int,
    payload: FieldReportCreate,
    session: Annotated[Session, Depends(get_session)],
    user: OperatorUser,
) -> FieldReportOut:
    """Guarda el texto que el operador revisó y confirmó."""

    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    report = FieldReport(
        zone_id=zone.id,
        extracted_text=payload.extracted_text,
        confirmed_text=payload.confirmed_text,
        model_id=payload.model_id,
        source_filename=payload.source_filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        created_by=str(user.get("sub", "local")),
        status="confirmed",
    )
    session.add(report)
    session.commit()
    return FieldReportOut.model_validate(report)


@app.get("/api/v1/zones/{zone_id}/field-reports", response_model=list[FieldReportOut])
def list_field_reports(
    zone_id: int,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[FieldReportOut]:
    zone = session.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    reports = session.scalars(
        select(FieldReport)
        .where(FieldReport.zone_id == zone_id)
        .order_by(FieldReport.id.desc())
        .limit(limit)
    ).all()
    return [FieldReportOut.model_validate(report) for report in reports]
