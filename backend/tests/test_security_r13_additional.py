from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

# Contexto de hash para generar contraseñas seguras en los usuarios de prueba.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Cliente de pruebas para hacer peticiones HTTP contra la API.
client = TestClient(app)


def setup_r13_additional_user() -> None:
    """
    Prepara un único usuario de prueba para los casos negativos de seguridad de R13.

    Este archivo no repite todos los escenarios de R11 y R12.
    Solo añade los casos que faltaban:
    - login inválido
    - token inválido
    - token expirado
    """
    db = SessionLocal()

    try:
        # Limpiamos primero las tablas relacionadas para evitar restos de otras pruebas.
        db.execute(text("DELETE FROM refresh_tokens"))
        db.execute(text("DELETE FROM user_roles"))
        db.execute(text("DELETE FROM users"))
        db.commit()

        # Creamos un usuario mínimo de prueba.
        user_repo = UserRepository(db)
        user_repo.create(
            User(
                email="security@test.com",
                password_hash=pwd_context.hash("security123"),
                display_name="Usuario Seguridad",
            )
        )
    finally:
        db.close()


def login_and_get_access_token(email: str, password: str) -> str:
    """
    Hace login y devuelve únicamente el access token.

    Se usa como ayuda para no repetir el mismo bloque en varios tests.
    """
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_expired_access_token(user_id: str) -> str:
    """
    Genera manualmente un access token ya expirado.

    Esto permite comprobar el comportamiento ante expiración real
    sin tener que esperar a que pase el tiempo.
    """
    now = datetime.now(timezone.utc)

    # Marcamos una expiración pasada para simular un token caducado.
    expired_at = now - timedelta(minutes=5)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int((now - timedelta(minutes=10)).timestamp()),
        "exp": int(expired_at.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def test_p13_1_invalid_login():
    """
    P13.1 - Prueba de login inválido.

    Verifica que el sistema rechaza credenciales incorrectas.
    """
    setup_r13_additional_user()

    response_login_invalid = client.post(
        "/auth/login",
        data={
            "username": "security@test.com",
            "password": "contrasena-incorrecta",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response_login_invalid.status_code == 401
    assert response_login_invalid.json()["detail"] == "Credenciales inválidas"


def test_p13_3_access_with_invalid_token():
    """
    P13.3 - Prueba de acceso con token inválido.

    Verifica que un token manipulado o inventado no permite acceder
    a endpoints protegidos.
    """
    setup_r13_additional_user()

    response_invalid_token = client.get(
        "/protected",
        headers={"Authorization": "Bearer token-falso-o-manipulado"},
    )

    assert response_invalid_token.status_code == 401
    assert response_invalid_token.json()["detail"] == "Token inválido"


def test_p13_3_access_with_expired_token():
    """
    P13.3 - Prueba de acceso con token expirado.

    Verifica que un token correctamente firmado pero caducado
    también es rechazado por el sistema.
    """
    setup_r13_additional_user()

    # Primero hacemos login normal para obtener el usuario real del sistema.
    valid_access_token = login_and_get_access_token(
        email="security@test.com",
        password="security123",
    )

    # Consultamos /auth/me para recuperar el ID real del usuario autenticado.
    response_me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_access_token}"},
    )

    assert response_me.status_code == 200
    user_id = response_me.json()["id"]

    # Construimos un token expirado para ese usuario.
    expired_access_token = create_expired_access_token(user_id=user_id)

    response_expired_token = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {expired_access_token}"},
    )

    assert response_expired_token.status_code == 401
    assert response_expired_token.json()["detail"] == "Token inválido"