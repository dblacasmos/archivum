from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ------------------
# Rutas del proyecto
# ------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """
    Carga la configuración desde el archivo .env
    o desde variables de entorno del sistema.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        extra="ignore",
    )

    # ----------------
    # Base de datos
    # ----------------
    database_url: str

    # ----------------
    # JWT / Auth
    # ----------------
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 15
    refresh_token_expires_days: int = 7

    # ----------------
    # Redis
    # ----------------
    redis_url: str = "redis://localhost:6379/0"

    # ----------------
    # Rate limiting
    # ----------------
    rate_limit_enabled: bool = True

    rate_limit_login_max_requests: int = 5
    rate_limit_login_window_seconds: int = 60

    rate_limit_query_max_requests: int = 20
    rate_limit_query_window_seconds: int = 60

    rate_limit_upload_max_requests: int = 10
    rate_limit_upload_window_seconds: int = 60


settings = Settings()