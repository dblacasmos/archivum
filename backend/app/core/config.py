from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# ------------------
# Rutas del proyecto
# ------------------

# config.py está en backend/app/core/config.py
# parents[2] -> carpeta "backend"
BACKEND_DIR = Path(__file__).resolve().parents[2]

# raíz del proyecto (archivum)
PROJECT_DIR = BACKEND_DIR.parent

# -------------------------------
# Configuración global (lee .env)
# -------------------------------

class Settings(BaseSettings):
    '''Carga la config desde el archivo .env
    o desde variables de entorno del sistema
    '''

    # dónde está el .env
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        extra="ignore"
    )

    # Variable obligatoria (.env debe contener DATABASE_URL)
    database_url: str

    # ------ JWT / Auth ------

    # clave secreta para firmar tokens
    jwt_secret_key: str = "dev_secret_change_me"

    # algoritmo de firma
    jwt_algorithm: str = "HS256"

    # minutos de vida del access token
    access_token_expires_minutes: int = 15

    # días de vida del refresh token
    resfresh_token_expires_days: int = 7


# Crea la config real leyendo el .env   
settings = Settings()