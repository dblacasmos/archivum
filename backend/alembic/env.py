from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Config principal de Alembic (lee alembic.ini)
config = context.config

# Usa la URL de la BD desde mi .env
# settings lee el .env y expone settings.database_url
from app.core.config import settings
# Sobreescribe sqlalchemy.url del alembic.ini con la URL real
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configura logging usando el archivo alembic.ini (si existe)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Le decimos a Alembic que 'metadata' usar para autogenerate
# Base.metadata contiene el catálogo de tablas definidas en los modelos
from app.core.db import Base
# Importar User fuerza a cargar el modelo y registrarlo en Base.metadata
from app.users.models import User

# Alembic usará estas tablas para comparar y generar migraciones
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Modo offline: NO abre conexión real. Solo genera SQL usando la URL configurada."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,     # Insertar valores literales en el SQL generado
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: SÍ abre conexión real y ejecuta migraciones en la BD."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,    # sin pool para migraciones
    )

    with connectable.connect() as connection:
        # Configura Alembic para ejecutar migraciones usando esta conexión
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


# Decide si se ejecuta offline u online según como se llama a Alembic
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()