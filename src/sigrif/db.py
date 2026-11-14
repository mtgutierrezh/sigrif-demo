import importlib
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def init_db() -> None:
    importlib.import_module("sigrif.models")
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE readings ADD COLUMN IF NOT EXISTS risk_level VARCHAR(10)")
        )
        connection.execute(
            text("ALTER TABLE readings ADD COLUMN IF NOT EXISTS risk_score DOUBLE PRECISION")
        )
        connection.execute(
            text(
                "ALTER TABLE readings ADD COLUMN IF NOT EXISTS historical_fires "
                "INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE readings ADD COLUMN IF NOT EXISTS source "
                "VARCHAR(20) NOT NULL DEFAULT 'manual'"
            )
        )
        connection.execute(
            text("ALTER TABLE readings ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_readings_zone_observed "
                "ON readings (zone_id, observed_at) WHERE observed_at IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS vegetation "
                "DOUBLE PRECISION NOT NULL DEFAULT 0.3"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS historical_fires "
                "INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS slope "
                "DOUBLE PRECISION NOT NULL DEFAULT 15"
            )
        )
        for column in (
            "fuel_native",
            "fuel_plantation",
            "fuel_shrub",
            "fuel_grass",
            "fuel_agriculture",
            "fuel_urban",
        ):
            connection.execute(
                text(
                    f"ALTER TABLE zones ADD COLUMN IF NOT EXISTS {column} "
                    "DOUBLE PRECISION NOT NULL DEFAULT 0"
                )
            )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS dominant_fuel "
                "VARCHAR(30) NOT NULL DEFAULT 'Sin dato'"
            )
        )
        connection.execute(
            text("ALTER TABLE zones ADD COLUMN IF NOT EXISTS last_source VARCHAR(20)")
        )
        connection.execute(
            text("ALTER TABLE zones ADD COLUMN IF NOT EXISTS last_alert_at TIMESTAMPTZ")
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS provincia "
                "VARCHAR(80) NOT NULL DEFAULT 'Valparaíso'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS region "
                "VARCHAR(80) NOT NULL DEFAULT 'Valparaíso'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS zone_type "
                "VARCHAR(30) NOT NULL DEFAULT 'sector_municipal'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS name_source "
                "VARCHAR(120) NOT NULL DEFAULT 'desconocida'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE zones ADD COLUMN IF NOT EXISTS name_official "
                "BOOLEAN NOT NULL DEFAULT false"
            )
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_alerts_zone_status ON alerts (zone_id, status)")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_alerts_created_at ON alerts (created_at)")
        )
        connection.execute(
            text(
                "UPDATE zones SET "
                "vegetation = round((0.15 + ((id * 37) % 70) / 100.0)::numeric, 2), "
                "historical_fires = (id * 7) % 12, "
                "slope = 5 + ((id * 13) % 35) "
                "WHERE last_source IS NULL"
            )
        )
