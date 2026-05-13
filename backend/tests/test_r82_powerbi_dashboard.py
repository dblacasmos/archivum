from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

client = TestClient(app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r82() -> None:
    """
    Limpia los datos necesarios para que el test R82 sea repetible.
    """

    db = SessionLocal()

    try:
        db.execute(text("DELETE FROM tracking_events"))
        db.execute(text("DELETE FROM user_roles"))
        db.execute(text("DELETE FROM refresh_tokens"))
        db.execute(text("DELETE FROM users"))
        db.commit()

    finally:
        db.close()


def create_r82_user(email: str, password: str, display_name: str) -> User:
    """
    Crea un usuario de prueba para generar eventos.
    """

    db = SessionLocal()

    try:
        repository = UserRepository(db)

        user = User(
            email=email,
            password_hash=pwd_context.hash(password),
            display_name=display_name,
            is_active=True,
        )

        return repository.create(user)

    finally:
        db.close()


def login_r82_user(email: str, password: str) -> str:
    """
    Hace login y devuelve un access token válido.
    """

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_p82_1_powerbi_events_are_exported_as_csv():
    """
    P82.1 - Prueba de visualización.

    Verifica que:
    - existen eventos registrados
    - el endpoint analítico devuelve CSV
    - el CSV contiene columnas útiles para Power BI
    """

    reset_database_for_r82()

    create_r82_user(
        email="powerbi_r82@test.com",
        password="powerbi123",
        display_name="Usuario Power BI R82",
    )

    token = login_r82_user(
        email="powerbi_r82@test.com",
        password="powerbi123",
    )

    response = client.post(
        "/tracking/events",
        json={
            "event_type": "query_executed",
            "source": "query",
            "payload": {
                "query": "contrato laboral",
                "search_mode": "hybrid",
                "results_count": 3,
            },
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201, response.text

    csv_response = client.get(
        "/analytics/powerbi/events.csv",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert csv_response.status_code == 200, csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")

    csv_text = csv_response.text

    assert "event_id,event_type,source,user_id,created_at,event_date,event_hour,query_text,search_mode,results_count" in csv_text
    assert "query_executed" in csv_text
    assert "contrato laboral" in csv_text
    assert "hybrid" in csv_text
    assert "3" in csv_text


def test_p82_2_powerbi_events_are_exported_as_json():
    """
    Verifica que el modelo analítico también se puede consultar en JSON.
    """

    reset_database_for_r82()

    create_r82_user(
        email="powerbi_json_r82@test.com",
        password="powerbi123",
        display_name="Usuario Power BI JSON R82",
    )

    token = login_r82_user(
        email="powerbi_json_r82@test.com",
        password="powerbi123",
    )

    response = client.post(
        "/tracking/events",
        json={
            "event_type": "rag_executed",
            "source": "rag",
            "payload": {
                "query": "resumen del contrato",
                "search_mode": "semantic",
                "results_count": 2,
            },
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201, response.text

    analytics_response = client.get(
        "/analytics/powerbi/events",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert analytics_response.status_code == 200, analytics_response.text

    data = analytics_response.json()

    assert data["message"] == "Eventos preparados correctamente para Power BI"
    assert data["total"] == 1
    assert data["events"][0]["event_type"] == "rag_executed"
    assert data["events"][0]["source"] == "rag"
    assert data["events"][0]["query_text"] == "resumen del contrato"
    assert data["events"][0]["search_mode"] == "semantic"
    assert data["events"][0]["results_count"] == 2
    assert data["events"][0]["event_date"]
    assert isinstance(data["events"][0]["event_hour"], int)