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

client = TestClient(app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def clean_document_storage() -> None:
    """
    Limpia la carpeta de almacenamiento para que la prueba
    empiece siempre desde cero.
    """
    upload_dir = Path(settings.upload_dir)

    if upload_dir.exists():
        shutil.rmtree(upload_dir)


def reset_database_for_r31() -> None:
    """
    Reinicia las tablas necesarias para probar chunking.
    """
    db = SessionLocal()

    try:
        db.execute(text("DELETE FROM document_chunks"))
        db.execute(text("DELETE FROM document_versions"))
        db.execute(text("DELETE FROM document_metadata"))
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
                (gen_random_uuid(), 'editor', 'Editor documental'),
                (gen_random_uuid(), 'viewer', 'Lector de documentos');
                """
            )
        )
        db.commit()

        user_repo = UserRepository(db)

        editor_user = user_repo.create(
            User(
                email="r31_editor@test.com",
                password_hash=pwd_context.hash("123456"),
                display_name="Editor R31",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        user_repo.assign_role(editor_user, editor_role)

    finally:
        db.close()


def login_and_get_token(email: str, password: str) -> str:
    """
    Hace login y devuelve el access token del usuario.
    """
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def upload_document(token: str, title: str, filename: str, content: bytes, mime_type: str) -> dict:
    """
    Sube un documento al sistema.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title},
        files={"file": (filename, content, mime_type)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def extract_text(token: str, document_id: str, version_number: int) -> dict:
    """
    Ejecuta la extracción previa, necesaria antes del chunking.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def chunk_text(token: str, document_id: str, version_number: int, chunk_size: int, chunk_overlap: int) -> dict:
    """
    Lanza la fragmentación del texto ya extraído.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        params={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def get_chunks(token: str, document_id: str, version_number: int) -> dict:
    """
    Recupera los chunks ya guardados en base de datos.
    """
    response = client.get(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def test_p31_1_chunk_text_and_persist_chunks_correctly():
    """
    P31.1 - Verifica que el texto extraído se divide en varios chunks
    y que todos quedan persistidos y ordenados.
    """
    clean_document_storage()
    reset_database_for_r31()

    token = login_and_get_token("r31_editor@test.com", "123456")

    long_text = (
        "Este es un texto de prueba para validar el chunking en Archivum. "
        "Necesitamos suficiente longitud para obligar al sistema a partirlo en varios fragmentos. "
        "Cada chunk debe mantener el orden lógico del texto y un pequeño solapamiento entre segmentos. "
        "De esta forma, el requisito R31 queda validado antes de pasar a embeddings y búsqueda semántica. "
    ) * 4

    document = upload_document(
        token=token,
        title="Manual R31",
        filename="manual_r31.txt",
        content=long_text.encode("utf-8"),
        mime_type="text/plain",
    )

    document_id = document["id"]

    extraction = extract_text(token=token, document_id=document_id, version_number=1)
    assert extraction["extraction_status"] == "completed"

    chunking = chunk_text(
        token=token,
        document_id=document_id,
        version_number=1,
        chunk_size=180,
        chunk_overlap=40,
    )

    assert chunking["document_id"] == document_id
    assert chunking["version_number"] == 1
    assert chunking["chunk_size"] == 180
    assert chunking["chunk_overlap"] == 40
    assert chunking["total_chunks"] >= 2
    assert len(chunking["items"]) == chunking["total_chunks"]

    first_chunk = chunking["items"][0]
    second_chunk = chunking["items"][1]

    assert first_chunk["chunk_index"] == 0
    assert first_chunk["char_count"] <= 180
    assert first_chunk["start_char"] < first_chunk["end_char"]

    assert second_chunk["chunk_index"] == 1
    assert second_chunk["start_char"] < second_chunk["end_char"]
    assert second_chunk["start_char"] < first_chunk["end_char"]

    stored_chunks = get_chunks(
        token=token,
        document_id=document_id,
        version_number=1,
    )

    assert stored_chunks["total_chunks"] == chunking["total_chunks"]
    assert stored_chunks["items"][0]["content"] == chunking["items"][0]["content"]

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT chunk_index, char_count, start_char, end_char
                FROM document_chunks
                WHERE document_id = :document_id
                ORDER BY chunk_index ASC
                """
            ),
            {"document_id": document_id},
        ).mappings().all()

        assert len(rows) == chunking["total_chunks"]
        assert rows[0]["chunk_index"] == 0
        assert rows[0]["char_count"] <= 180
    finally:
        db.close()