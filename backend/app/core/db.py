from collections.abc import Generator

from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Motor de SQLAlchemy conectado a la base de datos definida en .env
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Registramos el tipo vector en cada nueva conexión de Psycopg.
# Esto permite leer y escribir columnas pgvector correctamente.
@event.listens_for(engine, "connect")
def register_pgvector_types(dbapi_connection, connection_record) -> None:
    """
    Registra el tipo vector de pgvector en cada conexión nueva.
    """
    register_vector(dbapi_connection)


# Fábrica de sesiones síncronas.
# Tu proyecto actual usa SQLAlchemy síncrono, no AsyncSession.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Clase base de la que heredarán todos los modelos."""

    pass


def get_session() -> Generator[Session, None, None]:
    """
    Dependency de FastAPI para abrir y cerrar una sesión por petición.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()