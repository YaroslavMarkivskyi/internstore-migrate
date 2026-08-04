from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    internal_token_secret: str
    orders_service_url: str
    inventory_service_url: str
    catalog_service_url: str
    telemetry_service_url: str
    security_service_url: str
    chat_service_url: str
    # ai-assistant's own database — search_products queries its
    # product_embeddings table directly (pgvector) rather than adding a
    # public HTTP endpoint to ai-assistant just for this.
    ai_db_url: str
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    http_timeout_seconds: float = 10.0


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
