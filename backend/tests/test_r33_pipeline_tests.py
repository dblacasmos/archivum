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

# Cliente HTTP de pruebas para llamar a la API como si fuera un usuario real.
client = TestClient(app)

# Contexto para generar hashes de contraseña seguros en los usuarios de prueba.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def clean_document_storage() -> None:
    """
    Limpia la carpeta de subida para que cada prueba
    empiece sin archivos residuales de otras ejecuciones.
    """
    upload_dir = Path(settings.upload_dir)

    if upload_dir.exists():
        shutil.rmtree(upload_dir)


def reset_database_for_r33() -> None:
    """
    Deja la base de datos en un estado mínimo y controlado
    para las pruebas integradas del pipeline.
    """
    db = SessionLocal()

    try:
        # Borramos de lo más dependiente a lo más base.
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

        # Creamos solo los roles que el proyecto ya usa.
        db.execute(
            text(
                """
                INSERT INTO roles (id, name, description) VALUES
                (gen_random_uuid(), 'admin', 'Administrador del sistema'),
                (gen_random_uuid(), 'editor', 'Editor documental'),
                (gen_random_uuid(), 'viewer', 'Lector documental');
                """
            )
        )
        db.commit()

        user_repo = UserRepository(db)

        owner_user = user_repo.create(
            User(
                email="r33_owner@test.com",
                password_hash=pwd_context.hash("123456"),
                display_name="Owner R33",
            )
        )

        viewer_user = user_repo.create(
            User(
                email="r33_viewer@test.com",
                password_hash=pwd_context.hash("123456"),
                display_name="Viewer R33",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        viewer_role = user_repo.get_role_by_name("viewer")

        user_repo.assign_role(owner_user, editor_role)
        user_repo.assign_role(viewer_user, viewer_role)

    finally:
        db.close()


def login_and_get_token(email: str, password: str) -> str:
    """
    Hace login en la API y devuelve el access token.
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
    Sube un documento nuevo al sistema.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title},
        files={"file": (filename, content, mime_type)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def share_document(token: str, document_id: str, target_user_id: str) -> dict:
    """
    Comparte un documento con otro usuario para probar
    lectura autorizada del job del pipeline.
    """
    response = client.post(
        f"/documents/{document_id}/share",
        json={"user_id": target_user_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def start_pipeline(token: str, document_id: str, version_number: int, chunk_size: int, chunk_overlap: int) -> dict:
    """
    Lanza el pipeline asíncrono para una versión concreta.
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


def get_extracted_text(token: str, document_id: str, version_number: int) -> dict:
    """
    Recupera el texto extraído persistido para una versión.
    """
    response = client.get(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def get_chunks(token: str, document_id: str, version_number: int) -> dict:
    """
    Recupera los chunks ya persistidos de una versión.
    """
    response = client.get(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def wait_until_job_finishes(token: str, job_id: str, timeout_seconds: float = 3.0) -> tuple[dict, list[str], list[str]]:
    """
    Espera a que el job termine y además guarda el rastro
    de estados y pasos vistos durante el polling.
    """
    start = time.time()
    seen_statuses: list[str] = []
    seen_steps: list[str] = []
    last_response: dict | None = None

    while time.time() - start < timeout_seconds:
        last_response = get_pipeline_job(token=token, job_id=job_id)

        seen_statuses.append(last_response["status"])
        seen_steps.append(last_response["current_step"])

        if last_response["status"] in {"completed", "failed"}:
            return last_response, seen_statuses, seen_steps

        time.sleep(0.1)

    assert last_response is not None, "No se pudo recuperar el estado final del job"
    return last_response, seen_statuses, seen_steps


def get_user_id_by_email(email: str) -> str:
    """
    Busca directamente en base de datos el ID de un usuario.
    Esto simplifica la preparación de datos de prueba.
    """
    db = SessionLocal()

    try:
        row = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        ).mappings().one()

        return str(row["id"])
    finally:
        db.close()


def test_p33_1_end_to_end_pipeline_processes_document_completely():
    """
    P33.1 - Comprueba el flujo end-to-end completo:
    subida, lanzamiento del pipeline, finalización correcta,
    texto extraído persistido y chunks generados.
    """
    clean_document_storage()
    reset_database_for_r33()

    owner_token = login_and_get_token("r33_owner@test.com", "123456")

    source_text = (
        "Archivum procesa documentos de forma asíncrona para extraer texto y dividirlo en fragmentos útiles. "
        "Este caso de prueba valida el flujo completo del pipeline y su persistencia final en base de datos. "
    ) * 5

    document = upload_document(
        token=owner_token,
        title="Documento R33 E2E",
        filename="documento_r33_e2e.txt",
        content=source_text.encode("utf-8"),
        mime_type="text/plain",
    )

    started_job = start_pipeline(
        token=owner_token,
        document_id=document["id"],
        version_number=1,
        chunk_size=150,
        chunk_overlap=30,
    )

    final_job, _, _ = wait_until_job_finishes(
        token=owner_token,
        job_id=started_job["job"]["id"],
    )

    extracted_text_response = get_extracted_text(
        token=owner_token,
        document_id=document["id"],
        version_number=1,
    )

    chunks_response = get_chunks(
        token=owner_token,
        document_id=document["id"],
        version_number=1,
    )

    assert final_job["status"] == "completed"
    assert final_job["current_step"] == "ready_for_vectorization"
    assert final_job["ready_for_vectorization"] is True
    assert final_job["total_chunks"] == chunks_response["total_chunks"]

    assert extracted_text_response["extraction_status"] == "completed"
    assert extracted_text_response["characters_count"] == len(extracted_text_response["extracted_text"])
    assert extracted_text_response["extracted_text"].strip() == source_text.strip()

    assert chunks_response["total_chunks"] >= 2
    assert chunks_response["items"][0]["chunk_index"] == 0
    assert chunks_response["items"][-1]["chunk_index"] == chunks_response["total_chunks"] - 1

    db = SessionLocal()
    try:
        db_summary = db.execute(
            text(
                """
                SELECT
                    dv.extraction_status,
                    LENGTH(dv.extracted_text) AS extracted_length,
                    COUNT(dc.id) AS total_chunks
                FROM document_versions dv
                LEFT JOIN document_chunks dc
                    ON dc.document_version_id = dv.id
                WHERE dv.document_id = :document_id
                  AND dv.version_number = 1
                GROUP BY dv.extraction_status, dv.extracted_text
                """
            ),
            {"document_id": document["id"]},
        ).mappings().one()

        assert db_summary["extraction_status"] == "completed"
        assert db_summary["extracted_length"] == len(extracted_text_response["extracted_text"])
        assert db_summary["total_chunks"] == chunks_response["total_chunks"]
    finally:
        db.close()


def test_p33_2_pipeline_state_transitions_are_consistent_for_success_and_failure():
    """
    P33.2 - Verifica la coherencia de estados del pipeline:
    caso exitoso y caso fallido por formato no soportado.
    """
    clean_document_storage()
    reset_database_for_r33()

    owner_token = login_and_get_token("r33_owner@test.com", "123456")

    success_document = upload_document(
        token=owner_token,
        title="Documento R33 estados OK",
        filename="documento_r33_ok.txt",
        content=b"Texto sencillo para validar estados correctos del pipeline.",
        mime_type="text/plain",
    )

    success_job = start_pipeline(
        token=owner_token,
        document_id=success_document["id"],
        version_number=1,
        chunk_size=80,
        chunk_overlap=10,
    )

    success_final_job, seen_statuses, seen_steps = wait_until_job_finishes(
        token=owner_token,
        job_id=success_job["job"]["id"],
    )

    assert success_job["job"]["status"] in {"pending", "running", "completed"}
    assert success_final_job["status"] == "completed"
    assert success_final_job["current_step"] == "ready_for_vectorization"
    assert all(status in {"pending", "running", "completed"} for status in seen_statuses)
    assert all(step in {"queued", "extracting_text", "chunking_text", "ready_for_vectorization"} for step in seen_steps)

    failed_document = upload_document(
        token=owner_token,
        title="Documento R33 estados KO",
        filename="documento_r33_ko.doc",
        content=b"Binario simulado no soportado",
        mime_type="application/msword",
    )

    failed_job = start_pipeline(
        token=owner_token,
        document_id=failed_document["id"],
        version_number=1,
        chunk_size=80,
        chunk_overlap=10,
    )

    failed_final_job, failed_statuses, failed_steps = wait_until_job_finishes(
        token=owner_token,
        job_id=failed_job["job"]["id"],
    )

    assert failed_final_job["status"] == "failed"
    assert failed_final_job["current_step"] == "extracting_text"
    assert failed_final_job["ready_for_vectorization"] is False
    assert failed_final_job["error_message"] is not None
    assert "no está soportada" in failed_final_job["error_message"].lower()
    assert all(status in {"pending", "running", "failed"} for status in failed_statuses)
    assert all(step in {"queued", "extracting_text"} for step in failed_steps)


def test_p33_3_extracted_text_chunks_and_job_state_remain_consistent():
    """
    P33.3 - Valida la coherencia entre el texto extraído,
    la secuencia de chunks y el estado final del job.
    """
    clean_document_storage()
    reset_database_for_r33()

    owner_token = login_and_get_token("r33_owner@test.com", "123456")
    viewer_token = login_and_get_token("r33_viewer@test.com", "123456")
    viewer_user_id = get_user_id_by_email("r33_viewer@test.com")

    source_text = (
        "Uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince. "
        "Archivum mantiene trazabilidad entre texto extraído, fragmentos persistidos y estado del pipeline. "
    ) * 4

    document = upload_document(
        token=owner_token,
        title="Documento R33 coherencia",
        filename="documento_r33_coherencia.txt",
        content=source_text.encode("utf-8"),
        mime_type="text/plain",
    )

    share_document(
        token=owner_token,
        document_id=document["id"],
        target_user_id=viewer_user_id,
    )

    started_job = start_pipeline(
        token=owner_token,
        document_id=document["id"],
        version_number=1,
        chunk_size=120,
        chunk_overlap=20,
    )

    final_job, _, _ = wait_until_job_finishes(
        token=owner_token,
        job_id=started_job["job"]["id"],
    )

    extracted_text_response = get_extracted_text(
        token=viewer_token,
        document_id=document["id"],
        version_number=1,
    )

    chunks_response = get_chunks(
        token=viewer_token,
        document_id=document["id"],
        version_number=1,
    )

    viewer_job_response = get_pipeline_job(
        token=viewer_token,
        job_id=started_job["job"]["id"],
    )

    extracted_text = extracted_text_response["extracted_text"]
    chunk_items = chunks_response["items"]

    assert final_job["status"] == "completed"
    assert viewer_job_response["status"] == "completed"
    assert viewer_job_response["ready_for_vectorization"] is True
    assert viewer_job_response["total_chunks"] == len(chunk_items)

    assert len(chunk_items) >= 2

    previous_end = -1

    for expected_index, chunk in enumerate(chunk_items):
        # El índice debe ir en orden perfecto: 0, 1, 2...
        assert chunk["chunk_index"] == expected_index

        # El tamaño declarado del chunk debe coincidir con su contenido real.
        assert chunk["char_count"] == len(chunk["content"])

        # El contenido del chunk debe coincidir exactamente con el trozo
        # del texto extraído delimitado por start_char y end_char.
        assert chunk["content"] == extracted_text[chunk["start_char"]:chunk["end_char"]]

        # Cada chunk debe avanzar sobre el texto original.
        assert chunk["start_char"] >= 0
        assert chunk["end_char"] > chunk["start_char"]
        assert chunk["start_char"] < len(extracted_text)
        assert chunk["end_char"] <= len(extracted_text)

        # Permitimos solapamiento, pero no saltos absurdos hacia atrás.
        assert chunk["end_char"] > previous_end or chunk["start_char"] <= previous_end
        previous_end = max(previous_end, chunk["end_char"])

    # El último chunk debe terminar exactamente al final del texto.
    assert chunk_items[-1]["end_char"] == len(extracted_text)