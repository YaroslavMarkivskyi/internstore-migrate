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
    # STR-161b: replaces openai_api_key — Gemini via the Gemini Enterprise
    # Agent Platform authenticates with IAM/Workload Identity, no API key.
    # Must match ai-assistant's own gcp_project/gcp_location (config.py) —
    # both services embed with the same model into the same pgvector index.
    gcp_project: str
    gcp_location: str = "global"
    embedding_model: str = "gemini-embedding-001"
    # STR-161b: kept at 1536 via Gemini's Matryoshka truncation rather than
    # the model's native 3072 — see ai-assistant/src/ai_assistant/config.py
    # for the full rationale. Must match models.EMBEDDING_DIMENSIONS and
    # ai-assistant's embedding_dimensions exactly, since both write into the
    # same product_embeddings table.
    embedding_dimensions: int = 1536
    http_timeout_seconds: float = 10.0


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
