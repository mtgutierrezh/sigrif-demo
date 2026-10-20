from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sigrif:sigrif@localhost:5432/sigrif"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    sns_topic_arn: str | None = None
    sqs_queue_url: str | None = None
    log_level: str = "INFO"


settings = Settings()
