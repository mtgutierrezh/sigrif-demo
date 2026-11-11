from __future__ import annotations

import argparse
import logging
import time

from ..config import settings
from ..db import SessionLocal, init_db
from .service import run_ingestion

logger = logging.getLogger(__name__)


def once(provider: str | None = None) -> int:
    init_db()
    with SessionLocal() as session:
        run = run_ingestion(session, provider)
    logger.info(
        "ingesta provider=%s status=%s total=%s ok=%s failed=%s duration_ms=%s",
        run.provider,
        run.status,
        run.zones_total,
        run.zones_ok,
        run.zones_failed,
        run.duration_ms,
    )
    return 0 if run.status in {"ok", "partial"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta meteorológica de SIGRIF")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola pasada")
    parser.add_argument("--provider", choices=["auto", "dmc", "open_meteo", "synthetic"])
    args = parser.parse_args()
    logging.basicConfig(level=settings.log_level)
    if args.once:
        return once(args.provider)
    interval = max(60, settings.ingest_interval_seconds)
    logger.info("ingesta en bucle cada %s segundos", interval)
    while True:
        try:
            once(args.provider)
        except Exception:
            logger.exception("error no controlado en la ingesta")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
