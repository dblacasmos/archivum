from sqlalchemy import text

from app.core.db import SessionLocal
from app.users.models import User
from app.users.repository import UserRepository

def test_user_persistence():
    '''Test básico:
    1. Guarda un usuario en la BD
    2. Lo recupera
    3. Comprueba que los datos coinciden
    '''

    # Abre una sesión (conexión con la base de datos)
    db = SessionLocal()

    try:
        # Limpiar la tabla para que el test sea repetible
        db.execute(text("DELETE from users"))
        db.commit()

        # Crear repositorio usando la sesión actual
        repo = UserRepository(db)

        # Crear un nuevo usuario en memoria (todavía no está en la BD)
        user = User(
            email="david@test.com",
            password_hash="hash_fake",
            display_name="David"
        )

        # Guardar el usuario en PostgreSQL
        saved = repo.create(user)

        # Comprobar que se generó un ID
        assert saved.id is not None

        # Buscar el usuario por email
        found = repo.find_by_email("david@test.com")

        # Comprobar que existe
        assert found is not None

        # Valida datos clave
        assert found.email == "david@test.com"
        assert found.password_hash == "hash_fake"
        assert found.display_name == "David"
        
    finally:
        # Cierra la sesión pase lo que pase
        db.close()