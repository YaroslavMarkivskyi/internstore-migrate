from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    kafka_bootstrap_servers: str
    redis_url: str
    chat_service_url: str
    orders_service_url: str
    # Not yet consumed by this service's own code — see STR-137's ticket
    # notes on the follow-up (STR-138) that swaps context.py's direct
    # OrdersClient/CatalogClient calls for MCP tool calls through this.
    mcp_gateway_url: str | None = None
    openai_api_key: str
    chat_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    # Default mode when chat:{room_id}:mode is missing from Redis — matches
    # rooms.ai_mode's own server_default of true.
    ai_mode_default: str = "ai"
    ai_rate_limit: int = 10
    ai_rate_limit_window_seconds: int = 3600
    conversation_history_limit: int = 20
    order_history_limit: int = 5
    product_context_limit: int = 5
    max_response_tokens: int = 500


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
