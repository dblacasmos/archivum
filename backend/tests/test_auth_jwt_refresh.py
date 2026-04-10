from passlib.context import CryptContext
from sqlalchemy import text
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = TestClient(app)


def setup_test_user():
    """
    Limpia tablas y crea un usuario de prueba.
    """
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM refresh_tokens"))
        db.execute(text("DELETE FROM users"))
        db.commit()

        user_repo = UserRepository(db)
        user_repo.create(
            User(
                email="test@example.com",
                password_hash=pwd_context.hash("testpassword"),
                display_name="Usuario Test",
            )
        )
    finally:
        db.close()


def test_p11_1_login_and_protected_access():
    """
    P11.1:
    - login correcto
    - acceso correcto a endpoint protegido
    """
    setup_test_user()

    response_login = client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "testpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response_login.status_code == 200
    login_data = response_login.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["token_type"] == "bearer"

    access_token = login_data["access_token"]

    response_protected = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response_protected.status_code == 200
    protected_data = response_protected.json()
    assert protected_data["ok"] is True
    assert protected_data["email"] == "test@example.com"


def test_p11_2_refresh_token_rotation():
    """
    P11.2:
    - refresh correcto
    - el refresh antiguo ya no vale
    """
    setup_test_user()

    response_login = client.post(
        "/auth/login",
        data={"username": "test@example.com", "password": "testpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response_login.status_code == 200
    login_data = response_login.json()

    refresh_token = login_data["refresh_token"]

    response_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response_refresh.status_code == 200
    refresh_data = response_refresh.json()
    assert "access_token" in refresh_data
    assert "refresh_token" in refresh_data
    assert refresh_data["refresh_token"] != refresh_token

    response_old_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response_old_refresh.status_code == 401