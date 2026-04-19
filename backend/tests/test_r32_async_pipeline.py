import shutil
import time
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
    Limpia el directorio de subida para que cada prueba
    empiece sin restos de archivos previos.
    """
    upload_dir = Path(settings.upload_dir)

    if upload_dir.exists():
        shutil.rmtree(upload_dir)


def reset_database_for_r32() -> None:
    """
    Reinicia las tablas necesarias para probar el pipeline asíncrono.
    """
    db = SessionLocal()

    try:
        db.execute(text("DELETE FROM document_pipeline_jobs"))
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
                email="r32_editor@test.com",
                password_hash=pwd_context.hash("123456"),
                display_name="Editor R32",
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


def start_pipeline(
    token: str,
    document_id: str,
    version_number: int,
    chunk_size: int,
    chunk_overlap: int,
) -> dict:
    """
    Lanza el pipeline asíncrono.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/pipeline",
        params={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202, response.text
    return response.json()


def get_pipeline_job(token: str, job_id: str) -> dict:
    """
    Consulta el estado actual de un job del pipeline.
    """
    response = client.get(
        f"/documents/pipeline-jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def wait_until_job_finishes(token: str, job_id: str, timeout_seconds: float = 3.0) -> dict:
    """
    Espera hasta que el job termine en completed o failed.
    """
    start = time.time()
    last_response = None

    while time.time() - start < timeout_seconds:
        last_response = get_pipeline_job(token=token, job_id=job_id)

        if last_response["status"] in {"completed", "failed"}:
            return last_response

        time.sleep(0.1)

    assert last_response is not None, "No se pudo leer el estado del job"
    return last_response


def test_p32_1_run_pipeline_and_complete_all_steps():
    """
    P32.1 - Verifica que el pipeline ejecuta extracción, chunking
    y deja la versión lista para vectorización.
    """
    clean_document_storage()
    reset_database_for_r32()

    token = login_and_get_token("r32_editor@test.com", "123456")

    long_text = (
        "Este documento sirve para probar el pipeline asíncrono de Archivum. "
        "Primero debe extraerse el texto, después fragmentarse en chunks y por último "
        "quedar listo para la futura vectorización. "
    ) * 6

    document = upload_document(
        token=token,
        title="Documento R32",
        filename="documento_r32.txt",
        content=long_text.encode("utf-8"),
        mime_type="text/plain",
    )

    started_job = start_pipeline(
        token=token,
        document_id=document["id"],
        version_number=1,
        chunk_size=140,
        chunk_overlap=25,
    )

    assert started_job["message"] == "Pipeline lanzado correctamente en segundo plano"
    assert started_job["job"]["status"] in {"pending", "running", "completed"}
    assert started_job["job"]["current_step"] in {"queued", "extracting_text", "chunking_text", "ready_for_vectorization"}

    final_job = wait_until_job_finishes(
        token=token,
        job_id=started_job["job"]["id"],
    )

    assert final_job["status"] == "completed"
    assert final_job["current_step"] == "ready_for_vectorization"
    assert final_job["ready_for_vectorization"] is True
    assert final_job["total_chunks"] is not None
    assert final_job["total_chunks"] >= 2
    assert final_job["error_message"] is None

    db = SessionLocal()
    try:
        version_row = db.execute(
            text(
                """
                SELECT extraction_status, extracted_text
                FROM document_versions
                WHERE document_id = :document_id AND version_number = 1
                """
            ),
            {"document_id": document["id"]},
        ).mappings().one()

        chunk_count_row = db.execute(
            text(
                """
                SELECT COUNT(*) AS total
                FROM document_chunks
                WHERE document_id = :document_id
                """
            ),
            {"document_id": document["id"]},
        ).mappings().one()

        job_row = db.execute(
            text(
                """
                SELECT status, current_step, ready_for_vectorization, total_chunks
                FROM document_pipeline_jobs
                WHERE id = :job_id
                """
            ),
            {"job_id": started_job["job"]["id"]},
        ).mappings().one()

        assert version_row["extraction_status"] == "completed"
        assert version_row["extracted_text"] is not None
        assert chunk_count_row["total"] >= 2
        assert job_row["status"] == "completed"
        assert job_row["current_step"] == "ready_for_vectorization"
        assert job_row["ready_for_vectorization"] is True
        assert job_row["total_chunks"] >= 2
    finally:
        db.close()


def test_p32_2_mark_job_as_failed_when_extraction_fails():
    """
    Caso complementario:
    verifica que el job pasa a failed si la extracción no puede completarse.
    """
    clean_document_storage()
    reset_database_for_r32()

    token = login_and_get_token("r32_editor@test.com", "123456")

    document = upload_document(
        token=token,
        title="Documento DOC no soportado",
        filename="documento_r32.doc",
        content=b"Contenido binario simulado",
        mime_type="application/msword",
    )

    started_job = start_pipeline(
        token=token,
        document_id=document["id"],
        version_number=1,
        chunk_size=140,
        chunk_overlap=25,
    )

    final_job = wait_until_job_finishes(
        token=token,
        job_id=started_job["job"]["id"],
    )

    assert final_job["status"] == "failed"
    assert final_job["current_step"] == "extracting_text"
    assert final_job["ready_for_vectorization"] is False
    assert final_job["error_message"] is not None
    assert "no está soportada" in final_job["error_message"].lower()