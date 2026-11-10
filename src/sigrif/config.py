from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sigrif:sigrif@localhost:5432/sigrif"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    sns_topic_arn: str | None = None
    sqs_queue_url: str | None = None
    messaging_enabled: bool = True
    app_color: str = "local"
    ia_url: str = "http://localhost:8001"
    model_path: str = "artifacts/risk_model.joblib"
    model_s3_uri: str | None = None
    bedrock_enabled: bool = False
    bedrock_model_id: str = "amazon.nova-lite-v1:0"
    bedrock_timeout_seconds: float = 30.0
    ocr_max_bytes: int = 5 * 1024 * 1024
    ocr_max_tokens: int = 1500
    log_level: str = "INFO"
    auth_enabled: bool = False
    cognito_region: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    cors_origins: str = "http://localhost:5173"


settings = Settings()
