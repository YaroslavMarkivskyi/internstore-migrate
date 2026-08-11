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
    # STR-146: this service's first actual consumer of the Gateway — the
    # shopping ReAct loop (see react_loop.py) calls search_products/
    # get_cart/add_to_cart/remove_from_cart through here instead of a direct
    # Orders/Catalog HTTP call.
    mcp_gateway_url: str
    # STR-146: used to refresh the customer's internal-token mid-ReAct-loop
    # when it's close to its 60s TTL (see token_manager.py) — this service
    # has no other way to renew a token it didn't mint itself.
    auth_backend_url: str
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
    # STR-146: reuses STR-137's ReAct loop cap — a shopping conversation
    # shouldn't need more than a few search/add cycles.
    max_react_iterations: int = 5
    # How close to the internal-token's exp claim the loop waits before
    # proactively refreshing via auth-backend (see token_manager.py).
    token_refresh_margin_seconds: int = 15


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
