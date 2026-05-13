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

    # ----------------
    # Subida de documentos (R20)
    # ----------------
    upload_dir: str = str(PROJECT_DIR / "storage" / "documents")
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Lista simple de extensiones permitidas para mantener
    # la subida controlada y evitar formatos no contemplados.
    allowed_upload_extensions: str = ".pdf,.txt,.md,.doc,.docx"

    # ----------------
    # Embeddings (R40 / R41)
    # ----------------
    # Clave del proveedor externo de embeddings.
    openai_api_key: str | None = None

    # Modelo por defecto para generar embeddings.
    openai_embeddings_model: str = "text-embedding-3-small"

    # Número de dimensiones esperadas por el modelo configurado.
    # Lo dejamos explícito para que el esquema vectorial sea estable.
    openai_embeddings_dimensions: int = 1536

    # URL oficial del endpoint de embeddings.
    openai_embeddings_url: str = "https://api.openai.com/v1/embeddings"

    # Timeout para evitar que una petición colgada deje bloqueado el proceso.
    openai_embeddings_timeout_seconds: int = 60

    # Tamaño de lote para generar varios embeddings de una sola vez.
    openai_embeddings_batch_size: int = 32

    # ----------------
    # LLM / RAG (R70)
    # ----------------
    # Modelo usado para generar la respuesta final del flujo RAG.
    openai_chat_model: str = "gpt-4o-mini"

    # URL oficial del endpoint de chat completions.
    openai_chat_url: str = "https://api.openai.com/v1/chat/completions"

    # Timeout de la llamada al LLM para evitar bloqueos largos.
    openai_chat_timeout_seconds: int = 60

    # Temperatura baja para respuestas más estables y menos creativas.
    openai_chat_temperature: float = 0.2

    def get_allowed_upload_extensions(self) -> set[str]:
        """
        Convierte la cadena del .env en un conjunto de extensiones
        normalizadas en minúsculas.
        """
        return {
            item.strip().lower()
            for item in self.allowed_upload_extensions.split(",")
            if item.strip()
        }


settings = Settings()