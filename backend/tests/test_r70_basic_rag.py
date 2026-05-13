from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.main import app
from app.rag.llm_client import OpenAIChatClient
from app.users.models import User
from app.users.repository import UserRepository

client = TestClient(app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r70() -> None:
    """
    Limpia la base de datos para que el test R70 sea repetible.
    """
    db = SessionLocal()

    try:
        db.execute(text("DELETE FROM document_embeddings"))
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
                (gen_random_uuid(), 'editor', 'Puede crear y gestionar sus documentos'),
                (gen_random_uuid(), 'viewer', 'Puede consultar documentos autorizados');
                """
            )
        )
        db.commit()
    finally:
        db.close()


def create_user_with_role(
    email: str,
    password: str,
    display_name: str,
    role_name: str,
) -> str:
    """
    Crea un usuario con un rol concreto.
    """
    db = SessionLocal()

    try:
        user_repo = UserRepository(db)

        user = user_repo.create(
            User(
                email=email,
                password_hash=pwd_context.hash(password),
                display_name=display_name,
            )
        )

        role = user_repo.get_role_by_name(role_name)
        assert role is not None

        user_repo.assign_role(user, role)

        return str(user.id)
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


def upload_text_document(token: str, title: str, content: str) -> dict:
    """
    Crea un documento textual.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def add_document_metadata(
    token: str,
    document_id: str,
    key: str,
    value: str,
) -> None:
    """
    Añade metadata al documento.
    """
    response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": key, "value": value},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


def extract_text(token: str, document_id: str) -> None:
    """
    Extrae texto de la versión principal.
    """
    response = client.post(
        f"/documents/{document_id}/versions/1/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def chunk_text(token: str, document_id: str) -> None:
    """
    Divide el texto en chunks.
    """
    response = client.post(
        f"/documents/{document_id}/versions/1/chunk-text",
        params={"chunk_size": 300, "chunk_overlap": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def generate_embeddings(token: str, document_id: str) -> None:
    """
    Genera embeddings para los chunks del documento.
    """
    response = client.post(
        f"/documents/{document_id}/versions/1/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector artificial con una única posición activa.
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def fake_r70_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Sustituye OpenAI por embeddings controlados.

    Así el test no depende de internet ni de dinero, dos cosas que suelen
    fallar justo cuando más gracia hacen.
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "contrato" in normalized_text or "laboral" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "auditoría" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def fake_r70_llm_answer(self, prompt: str) -> str:
    """
    Respuesta falsa del LLM para validar el flujo RAG.
    """
    assert "Contrato laboral autorizado" in prompt
    assert "contrato laboral" in prompt.lower()

    return (
        "El contrato laboral autorizado contiene información relacionada "
        "con cláusulas laborales y condiciones del documento recuperado."
    )


def prepare_document_for_rag(
    token: str,
    title: str,
    content: str,
    metadata: dict[str, str],
) -> dict:
    """
    Crea un documento y lo deja listo para retrieval.
    """
    document = upload_text_document(
        token=token,
        title=title,
        content=content,
    )

    for key, value in metadata.items():
        add_document_metadata(
            token=token,
            document_id=document["id"],
            key=key,
            value=value,
        )

    extract_text(token=token, document_id=document["id"])
    chunk_text(token=token, document_id=document["id"])
    generate_embeddings(token=token, document_id=document["id"])

    return document


def test_r70_basic_rag_generates_answer_with_retrieved_context(monkeypatch):
    """
    P70.1 - Prueba de generación de respuesta con contexto recuperado.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r70_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_r70_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r70@test.com",
        password="editor123",
        display_name="Usuario R70",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r70@test.com",
        password="editor123",
    )

    document = prepare_document_for_rag(
        token=token,
        title="Contrato laboral autorizado",
        content=(
            "Contrato laboral autorizado con cláusulas laborales, "
            "condiciones de trabajo y obligaciones básicas."
        ),
        metadata={"category": "laboral"},
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato laboral",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "laboral"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["message"] == "Flujo RAG procesado correctamente"
    assert data["query"] == "contrato laboral"
    assert data["retrieved_chunks"] >= 1
    assert data["used_context_chunks"] >= 1
    assert data["used_context_chunks"] <= 5
    assert data["answer"]
    assert data["answer_status"] == "generated"
    assert data["fallback_applied"] is False
    assert data["prompt"]
    assert "Contrato laboral autorizado" in data["prompt"]
    assert "contrato laboral" in data["prompt"].lower()
    assert data["context"][0]["document_id"] == document["id"]

    assert data["hallucination_checks"]["enabled"] is True
    assert data["hallucination_checks"]["is_valid"] is True
    assert data["hallucination_checks"]["fallback_applied"] is False
    assert data["hallucination_checks"]["used_context_chunks"] >= 1
    assert data["hallucination_checks"]["used_context_chunks"] <= 5

    assert data["debug"]["rag_version"] == "basic_r74_latency_cost_metrics"
    assert data["debug"]["usage_metrics_enabled"] is True
    assert "usage_metrics" in data
    assert data["debug"]["citations_enabled"] is True
    assert data["debug"]["hallucination_control_enabled"] is True
    assert data["debug"]["evaluation_enabled"] is True
    assert "citations" in data
    assert len(data["citations"]) >= 1
    assert "evaluation" in data
    assert data["evaluation"]["enabled"] is True