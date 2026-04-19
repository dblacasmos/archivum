import shutil
from pathlib import Path

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


def setup_r20_data() -> None:
    """
    Prepara un usuario editor para poder subir documentos.

    También limpia las tablas relacionadas para que el test
    empiece desde un estado controlado.
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
                email="r20@test.com",
                password_hash=pwd_context.hash("r20password"),
                display_name="Usuario R20",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        user_repo.assign_role(editor_user, editor_role)

    finally:
        db.close()


def clean_r20_storage() -> None:
    """
    Elimina la carpeta de almacenamiento para que no queden restos
    de pruebas anteriores.
    """
    storage_dir = Path(settings.upload_dir)
    if storage_dir.exists():
        shutil.rmtree(storage_dir)


def login_and_get_access_token() -> str:
    """
    Hace login con el usuario editor y devuelve el access token.
    """
    response = client.post(
        "/auth/login",
        data={"username": "r20@test.com", "password": "r20password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_p20_1_document_upload_success():
    """
    P20.1:
    Verifica que un documento se sube correctamente,
    se registra en la base de datos y se almacena en disco.
    """
    clean_r20_storage()
    setup_r20_data()

    access_token = login_and_get_access_token()

    response = client.post(
        "/documents/upload",
        data={"title": "Manual de prueba"},
        files={
            "file": (
                "manual.txt",
                b"Este es un archivo de prueba para R20",
                "text/plain",
            )
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["title"] == "Manual de prueba"
    assert body["original_filename"] == "manual.txt"
    assert body["mime_type"] == "text/plain"
    assert body["size_bytes"] > 0
    assert body["owner_id"] is not None

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT original_filename, stored_filename, storage_path, mime_type, size_bytes
                FROM documents
                WHERE id = :document_id
                """
            ),
            {"document_id": body["id"]},
        ).mappings().first()

        assert row is not None
        assert row["original_filename"] == "manual.txt"
        assert row["stored_filename"] is not None
        assert row["storage_path"] is not None
        assert row["mime_type"] == "text/plain"
        assert row["size_bytes"] > 0

        saved_file_path = Path(row["storage_path"])
        assert saved_file_path.exists()
        assert saved_file_path.read_bytes() == b"Este es un archivo de prueba para R20"
    finally:
        db.close()