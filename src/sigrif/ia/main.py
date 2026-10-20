import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from prometheus_client import generate_latest
from sqlalchemy.orm import Session
from starlette.responses import Response

from ..db import SessionLocal, init_db
from ..events import delete_message, ensure_resources, receive_readings
from ..ml import risk_model
from ..models import Reading, Zone

logger = logging.getLogger(__name__)


def apply_reading(session: Session, payload: dict[str, Any]) -> bool:
    zone = session.get(Zone, payload["zone_id"])
    if zone is None:
        return False
    label, score = risk_model.predict(
        [
            payload["temperature"],
            payload["humidity"],
            payload["wind_speed"],
            payload["vegetation"],
            payload["slope"],
        ]
    )
    zone.risk_level = label
    zone.risk_score = score
    session.add(
        Reading(
            zone_id=zone.id,
            temperature=payload["temperature"],
            humidity=payload["humidity"],
            wind_speed=payload["wind_speed"],
            vegetation=payload["vegetation"],
            slope=payload["slope"],
        )
    )
    session.commit()
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
    threading.Thread(target=consume, daemon=True).start()
    yield


app = FastAPI(title="SIGRIF IA", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain")
