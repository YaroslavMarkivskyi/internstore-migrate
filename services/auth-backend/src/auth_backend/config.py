from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 3000
    # STR-155: Firebase project the external ID token must have been issued
    # for. Credentials themselves come from Application Default Credentials
    # (Workload Identity in GCP) — no service-account JSON key is loaded
    # from settings, see auth/external_token.py.
    firebase_project_id: str
    internal_token_secret: str
    internal_token_ttl_seconds: int = 60
    # Used by the guest cart session store (see auth/guest_session.py) —
    # mandatory since guest checkout depends on it.
    redis_url: str


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
