import shutil
from pathlib import Path

import fitz
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
    Limpia la carpeta de almacenamiento para evitar
    que un test reutilice archivos de otro.
    """
    upload_dir = Path(settings.upload_dir)

    if upload_dir.exists():
        shutil.rmtree(upload_dir)


def reset_database_for_r30() -> None:
    """
    Reinicia los datos mínimos necesarios para probar R30.
    """
    db = SessionLocal()

    try:
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
                email="r30_editor@test.com",
                password_hash=pwd_context.hash("123456"),
                display_name="Editor R30",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        user_repo.assign_role(editor_user, editor_role)

    finally:
        db.close()


def login_and_get_token(email: str, password: str) -> str:
    """
    Hace login y devuelve el access token.
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
    Lanza la extracción de texto para una versión concreta.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def get_extracted_text(token: str, document_id: str, version_number: int) -> dict:
    """
    Recupera el texto extraído ya persistido.
    """
    response = client.get(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def build_pdf_bytes(text_content: str) -> bytes:
    """
    Genera un PDF mínimo en memoria con PyMuPDF para probar
    la extracción sin depender de archivos externos.
    """
    pdf_document = fitz.open()
    page = pdf_document.new_page()
    page.insert_text((72, 72), text_content)

    pdf_bytes = pdf_document.tobytes()
    pdf_document.close()

    return pdf_bytes


def test_p30_1_extract_text_from_txt_version_and_persist_it():
    """
    P30.1 - Verifica extracción correcta desde un TXT
    y su persistencia en la versión correspondiente.
    """
    clean_document_storage()
    reset_database_for_r30()

    token = login_and_get_token("r30_editor@test.com", "123456")

    document = upload_document(
        token=token,
        title="Manual TXT",
        filename="manual_r30.txt",
        content=b"Primera linea del texto.\nSegunda linea del texto.",
        mime_type="text/plain",
    )

    document_id = document["id"]

    extraction = extract_text(
        token=token,
        document_id=document_id,
        version_number=1,
    )

    assert extraction["document_id"] == document_id
    assert extraction["version_number"] == 1
    assert extraction["extraction_status"] == "completed"
    assert "Primera linea del texto." in extraction["extracted_text"]
    assert "Segunda linea del texto." in extraction["extracted_text"]
    assert extraction["characters_count"] > 0

    extracted_text_response = get_extracted_text(
        token=token,
        document_id=document_id,
        version_number=1,
    )

    assert extracted_text_response["extracted_text"] == extraction["extracted_text"]

    db = SessionLocal()
    try:
        stored_version = db.execute(
            text(
                """
                SELECT extracted_text, extraction_status, extraction_error
                FROM document_versions
                WHERE document_id = :document_id AND version_number = 1
                """
            ),
            {"document_id": document_id},
        ).mappings().one()

        assert "Primera linea del texto." in stored_version["extracted_text"]
        assert stored_version["extraction_status"] == "completed"
        assert stored_version["extraction_error"] is None
    finally:
        db.close()


def test_p30_2_extract_text_from_pdf_version_and_persist_it():
    """
    Caso complementario:
    verifica extracción correcta desde PDF y persistencia.
    """
    clean_document_storage()
    reset_database_for_r30()

    token = login_and_get_token("r30_editor@test.com", "123456")
    pdf_bytes = build_pdf_bytes("Texto PDF de prueba para R30")

    document = upload_document(
        token=token,
        title="Manual PDF",
        filename="manual_r30.pdf",
        content=pdf_bytes,
        mime_type="application/pdf",
    )

    document_id = document["id"]

    extraction = extract_text(
        token=token,
        document_id=document_id,
        version_number=1,
    )

    assert extraction["document_id"] == document_id
    assert extraction["version_number"] == 1
    assert extraction["extraction_status"] == "completed"
    assert "Texto PDF de prueba para R30" in extraction["extracted_text"]
    assert extraction["characters_count"] > 0