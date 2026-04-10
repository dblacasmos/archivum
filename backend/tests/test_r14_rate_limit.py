from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = TestClient(app)


def setup_r14_data() -> None:
    """
    Prepara los datos mínimos para las pruebas de R14.

    Se limpian las tablas principales y se crean:
    - roles base
    - un usuario editor
    """
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
                email="ratelimit@test.com",
                password_hash=pwd_context.hash("editor123"),
                display_name="Usuario Rate Limit",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        user_repo.assign_role(editor_user, editor_role)
    finally:
        db.close()


def login_and_get_access_token() -> str:
    """
    Hace login con el usuario de pruebas y devuelve el access token.
    """
    response = client.post(
        "/auth/login",
        data={"username": "ratelimit@test.com", "password": "editor123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def reset_rate_limit_keys() -> None:
    """
    Limpia las claves de Redis usadas en las pruebas para evitar
    contaminación entre tests.
    """
    from app.core.redis_client import redis_client

    keys = redis_client.keys("rate_limit:*")
    if keys:
        redis_client.delete(*keys)


def test_p14_1_login_rate_limit_returns_429():
    """
    P14.1:
    Verifica que /auth/login devuelve 429 al superar el límite configurado.
    """
    setup_r14_data()
    reset_rate_limit_keys()

    last_response = None

    # El .env propone 5 peticiones de login por 60 segundos.
    # Las cinco primeras deben pasar y la siguiente debe caer con 429.
    for _ in range(6):
        last_response = client.post(
            "/auth/login",
            data={"username": "ratelimit@test.com", "password": "editor123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert "detail" in last_response.json()
    assert last_response.headers["X-RateLimit-Limit"] == "5"


def test_p14_1_query_rate_limit_returns_429():
    """
    P14.1:
    Verifica que /query devuelve 429 cuando el usuario autenticado
    supera el límite de consultas.
    """
    setup_r14_data()
    reset_rate_limit_keys()

    access_token = login_and_get_access_token()
    last_response = None

    # El .env propone 20 peticiones por 60 segundos.
    # La número 21 debe devolver 429.
    for index in range(21):
        last_response = client.post(
            "/query",
            json={"query": f"consulta-{index}"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert "detail" in last_response.json()
    assert last_response.headers["X-RateLimit-Limit"] == "20"


def test_p14_1_upload_rate_limit_returns_429():
    """
    P14.1:
    Verifica que /documents/upload devuelve 429 cuando el usuario
    autenticado supera el límite de subidas.
    """
    setup_r14_data()
    reset_rate_limit_keys()

    access_token = login_and_get_access_token()
    last_response = None

    # El .env propone 10 subidas por 60 segundos.
    # La número 11 debe devolver 429.
    for index in range(11):
        last_response = client.post(
            "/documents/upload",
            data={
                "title": f"Documento {index}",
                "content": "Contenido de prueba",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert "detail" in last_response.json()
    assert last_response.headers["X-RateLimit-Limit"] == "10"