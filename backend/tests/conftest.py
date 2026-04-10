import pytest
import redis

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limit_storage():
    """
    Limpia Redis antes y después de cada test para evitar que
    los contadores del rate limiting contaminen otras pruebas.

    Esto es importante porque varios tests reutilizan /auth/login
    y el rate limiting de R14 se aplica por IP.
    """
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    try:
        redis_client.flushdb()
    except Exception:
        # Si Redis no está disponible, no rompemos aquí.
        # Ya fallarán los tests que realmente dependan de Redis.
        pass

    yield

    try:
        redis_client.flushdb()
    except Exception:
        pass


@pytest.fixture
def setup_editor_user_and_token():
    """
    Crea un usuario editor y devuelve una función
    que hace login y entrega su access token.

    Se usa en las pruebas de observabilidad de R15
    para ejecutar /query con un usuario autenticado.
    """

    def _factory() -> str:
        db = SessionLocal()

        try:
            db.execute(text("DELETE FROM document_accesses"))
            db.execute(text("DELETE FROM documents"))
            db.execute(text("DELETE FROM user_roles"))
            db.execute(text("DELETE FROM refresh_tokens"))
            db.execute(text("DELETE FROM users"))
            db.execute(text("DELETE FROM roles"))
            db.commit()

            db.execute(
                text(
                    """
                    INSERT INTO roles (id, name, description) VALUES
                    (gen_random_uuid(), 'admin', 'Administrador del sistema'),
                    (gen_random_uuid(), 'editor', 'Puede crear y gestionar sus documentos'),
                    (gen_random_uuid(), 'viewer', 'Puede consultar documentos autorizados');
                    """
                )
            )
            db.commit()

            user_repo = UserRepository(db)

            editor_user = user_repo.create(
                User(
                    email="r15@test.com",
                    password_hash=pwd_context.hash("editor123"),
                    display_name="Usuario Observabilidad",
                )
            )

            editor_role = user_repo.get_role_by_name("editor")
            user_repo.assign_role(editor_user, editor_role)
        finally:
            db.close()

        response = client.post(
            "/auth/login",
            data={"username": "r15@test.com", "password": "editor123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    return _factory