from sqlalchemy import text

from app.core.db import SessionLocal
from app.users.models import User
from app.users.repository import UserRepository


def test_user_persistence():
    """
    Test básico:
    1. Guarda un usuario en la BD
    2. Lo recupera
    3. Comprueba que los datos coinciden
    """

    # Abre una sesión con la base de datos
    db = SessionLocal()

    try:
        # Limpiar tablas en orden correcto para evitar errores de claves foráneas
        db.execute(text("DELETE FROM refresh_tokens"))
        db.execute(text("DELETE FROM users"))
        db.commit()

        # Creamos el repositorio
        repo = UserRepository(db)

        # Creamos un usuario de prueba
        user = User(
            email="test@example.com",
            password_hash="hash_de_prueba",
            display_name="Usuario Test",
            is_active=True,
        )

        # Lo guardamos en base de datos
        created_user = repo.create(user)

        # Lo recuperamos por email
        recovered_user = repo.find_by_email("test@example.com")

        # Comprobaciones
        assert created_user.id is not None
        assert recovered_user is not None
        assert recovered_user.email == "test@example.com"
        assert recovered_user.display_name == "Usuario Test"
        assert recovered_user.is_active is True

    finally:
        db.close()