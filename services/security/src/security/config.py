from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    # Points at the mock-camera container in dev; a real ESP32-CAM base URL
    # replaces it in prod via this same env var.
    camera_base_url: str = "http://mock-camera:8001"
    # STR-140: OPA sidecar, same pod/network namespace on GKE (see
    # docker-compose.yml's security-opa for the local dev equivalent).
    opa_url: str = "http://localhost:8181"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
