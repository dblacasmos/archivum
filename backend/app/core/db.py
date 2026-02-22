from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

# Crea la conexión principal a la base de datos usando la URL del .env
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Fábrica de sesiones (cada sesión es una conversación con la DB)
# autocommit = False -> No guarda automáticamente
# autoflush = False -> No envía cambios antes de tiempo
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base que utilizarán todos los modelos (tablas)
class Base(DeclarativeBase):
    pass