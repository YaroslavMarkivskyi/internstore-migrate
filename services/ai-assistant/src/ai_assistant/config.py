from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    kafka_bootstrap_servers: str
    redis_url: str
    chat_service_url: str
    # STR-146: this service's first actual consumer of the Gateway — the ADK
    # agents call search_products / get_cart / add_to_cart / remove_from_cart
    # (and the read-only ops + guest tool tiers) through here over the real
    # MCP protocol instead of direct Orders/Catalog HTTP calls.
    mcp_gateway_url: str
    # STR-146: used to refresh the customer's internal-token mid-ReAct-loop
    # when it's close to its 60s TTL (see token_manager.py) — this service
    # has no other way to renew a token it didn't mint itself.
    auth_backend_url: str
    # STR-161b: no API key — Gemini via the Gemini Enterprise Agent Platform
    # (Vertex AI's Cloud Next 2026 rebrand) authenticates with IAM/Workload
    # Identity, same as every other GCP-native call this project makes.
    # `gcp_location` defaults to "global" per Google's current guidance for
    # the Gemini Enterprise API surface; override per-region if needed.
    gcp_project: str
    gcp_location: str = "global"
    # A current Vertex model id — the earlier "gemini-3-flash" default was
    # fictional (404 NOT_FOUND on Vertex) and only worked because every
    # environment overrode it via CHAT_MODEL. Keep this a real id so the
    # service is usable without the override.
    chat_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    # STR-161b: gemini-embedding-001 natively outputs 3072 dimensions:
    # https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-text-embeddings
    # Kept at 1536 here as a deliberate choice, not a leftover OpenAI
    # default — Gemini's Matryoshka Representation Learning supports
    # truncating to 768/1536/3072 with minimal quality loss (see
    # embeddings.py), so 1536 stays a supported size and this avoids the
    # Alembic column resize + full-catalog re-embed a 3072 switch would
    # force. Re-embedding is still required regardless (see README): the
    # OpenAI and Gemini embedding spaces aren't numerically compatible even
    # at matching dimensionality.
    embedding_dimensions: int = 1536
    # Default mode when chat:{room_id}:mode is missing from Redis — matches
    # rooms.ai_mode's own server_default of true.
    ai_mode_default: str = "ai"
    ai_rate_limit: int = 10
    ai_rate_limit_window_seconds: int = 3600
    conversation_history_limit: int = 20
    # Cross-session customer memory (PreloadMemoryTool + add_session_to_memory).
    # Off for demos on a tight Vertex embedding quota — each shopping turn
    # otherwise spends several extra embedding calls that search_products needs.
    memory_enabled: bool = True
    # STR-146: reuses STR-137's ReAct loop cap — a shopping conversation
    # shouldn't need more than a few search/add cycles.
    max_react_iterations: int = 5
    # How close to the internal-token's exp claim the loop waits before
    # proactively refreshing via auth-backend (see token_manager.py).
    token_refresh_margin_seconds: int = 15


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
