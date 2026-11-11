from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sigrif:sigrif@localhost:5432/sigrif"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    sns_topic_arn: str | None = None
    sqs_queue_url: str | None = None
    alert_topic_arn: str | None = None
    messaging_enabled: bool = True
    alert_cooldown_hours: int = 6
    app_color: str = "local"
    ia_url: str = "http://localhost:8001"
    model_path: str = "artifacts/risk_model.joblib"
    model_s3_uri: str | None = None
    bedrock_enabled: bool = False
    bedrock_model_id: str = "amazon.nova-lite-v1:0"
    bedrock_timeout_seconds: float = 30.0
    ocr_max_bytes: int = 5 * 1024 * 1024
    ocr_max_tokens: int = 1500
    ingest_enabled: bool = False
    ingest_provider: str = "auto"
    ingest_interval_seconds: int = 900
    ingest_station_radius_km: float = 80.0
    dmc_user: str | None = None
    dmc_token: str | None = None
    dmc_url: str = (
        "https://climatologia.meteochile.gob.cl/application/servicios/getDatosRecientesRedEma"
    )
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    log_level: str = "INFO"
    auth_enabled: bool = False
    cognito_region: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    cors_origins: str = "http://localhost:5173"

    @field_validator("aws_endpoint_url", mode="before")
    @classmethod
    def empty_endpoint_to_none(cls, value: str | None) -> str | None:
        return value or None


settings = Settings()
