from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 3000
    keycloak_issuer: str
    keycloak_jwks_uri: str
    internal_token_secret: str
    internal_token_ttl_seconds: int = 60
    # Used by the /logout denylist (see auth/revocation.py) and the guest
    # cart session store (see auth/guest_session.py) — mandatory since guest
    # checkout depends on it.
    redis_url: str


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
