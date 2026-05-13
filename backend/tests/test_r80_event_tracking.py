from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

# Cliente HTTP de pruebas para simular peticiones reales contra la API
client = TestClient(app)

# Utilidad para generar hashes de contraseña en usuarios de prueba
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r80() -> None:
    """
    Limpia los datos usados por R80 para que los tests sean repetibles.

    Se eliminan primero las tablas dependientes y después los usuarios.
    """
    db = SessionLocal()

    try:
        # Se eliminan primero los eventos porque dependen de users
        db.execute(text("DELETE FROM tracking_events"))

        # Se limpian relaciones y tokens asociados a usuarios
        db.execute(text("DELETE FROM user_roles"))
        db.execute(text("DELETE FROM refresh_tokens"))

        # Finalmente se eliminan los usuarios
        db.execute(text("DELETE FROM users"))

        # Se confirman los cambios
        db.commit()

    finally:
        db.close()


def create_r80_user(
    email: str,
    password: str,
    display_name: str,
) -> User:
    """
    Crea un usuario de prueba persistido en base de datos.
    """
    db = SessionLocal()

    try:
        repository = UserRepository(db)

        # Se crea el usuario con contraseña hasheada
        user = User(
            email=email,
            password_hash=pwd_context.hash(password),
            display_name=display_name,
            is_active=True,
        )

        # Se guarda el usuario en base de datos
        return repository.create(user)

    finally:
        db.close()


def login_r80_user(email: str, password: str) -> str:
    """
    Hace login y devuelve el access token JWT.

    El endpoint /auth/login utiliza OAuth2PasswordRequestForm,
    por lo que los datos deben enviarse como formulario.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    # Devuelve el token JWT generado por el backend
    return response.json()["access_token"]


def test_p80_1_tracking_event_is_registered_and_persisted():
    """
    P80.1 - Prueba de registro de eventos.

    Verifica que:
    - un usuario autenticado puede registrar un evento
    - el evento queda asociado al usuario correcto
    - el evento queda persistido en base de datos
    """
    reset_database_for_r80()

    # Se crea un usuario de prueba
    user = create_r80_user(
        email="tracking_r80@test.com",
        password="tracking123",
        display_name="Usuario Tracking R80",
    )

    # Se obtiene un token JWT válido
    token = login_r80_user(
        email="tracking_r80@test.com",
        password="tracking123",
    )

    # Se registra un evento mediante el endpoint protegido
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

    data = response.json()

    # Verificaciones básicas de la respuesta
    assert data["event_type"] == "query_executed"
    assert data["source"] == "query"
    assert data["user_id"] == str(user.id)

    # Verifica el contenido persistido en payload
    assert data["payload"]["query"] == "contrato laboral"
    assert data["payload"]["search_mode"] == "hybrid"
    assert data["payload"]["results_count"] == 3

    # Verifica que existe fecha de creación
    assert data["created_at"]

    db = SessionLocal()

    try:
        # Consulta directa a PostgreSQL para validar persistencia real
        stored_event = db.execute(
            text(
                """
                SELECT event_type, user_id, source, payload
                FROM tracking_events
                WHERE id = :event_id
                """
            ),
            {"event_id": data["id"]},
        ).mappings().one()

        # Validación de datos persistidos
        assert stored_event["event_type"] == "query_executed"
        assert str(stored_event["user_id"]) == str(user.id)
        assert stored_event["source"] == "query"
        assert stored_event["payload"]["query"] == "contrato laboral"

    finally:
        db.close()


def test_p80_2_user_can_list_own_tracking_events():
    """
    Verifica que un usuario autenticado puede consultar
    sus propios eventos registrados.
    """
    reset_database_for_r80()

    # Se crea el usuario de prueba
    create_r80_user(
        email="tracking_r80_list@test.com",
        password="tracking123",
        display_name="Usuario Tracking Lista R80",
    )

    # Login del usuario
    token = login_r80_user(
        email="tracking_r80_list@test.com",
        password="tracking123",
    )

    # Registro de un evento asociado al usuario
    create_response = client.post(
        "/tracking/events",
        json={
            "event_type": "rag_answer_generated",
            "source": "rag",
            "payload": {
                "answer_status": "generated",
                "used_context_chunks": 2,
            },
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert create_response.status_code == 201, create_response.text

    # Consulta de eventos recientes del usuario autenticado
    list_response = client.get(
        "/tracking/events",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert list_response.status_code == 200, list_response.text

    data = list_response.json()

    # Validaciones de estructura y contenido
    assert data["message"] == "Eventos recuperados correctamente"
    assert data["total"] == 1

    # Validación del evento recuperado
    assert data["events"][0]["event_type"] == "rag_answer_generated"
    assert data["events"][0]["source"] == "rag"
    assert data["events"][0]["payload"]["used_context_chunks"] == 2