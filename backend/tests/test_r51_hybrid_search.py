from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

client = TestClient(app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r51() -> None:
    """
    Limpia la base de datos para que el test sea repetible.
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


def create_user_with_role(email: str, password: str, display_name: str, role_name: str) -> None:
    """
    Crea un usuario de prueba con un rol concreto.
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
        assert role is not None, f"No se encontró el rol {role_name}"

        user_repo.assign_role(user, role)
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
    Sube un documento textual.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def extract_text(token: str, document_id: str, version_number: int) -> None:
    """
    Ejecuta extracción de texto.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def chunk_text(token: str, document_id: str, version_number: int) -> None:
    """
    Genera chunks grandes para que cada documento tenga un único fragmento.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        params={"chunk_size": 300, "chunk_overlap": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def generate_embeddings(token: str, document_id: str, version_number: int) -> None:
    """
    Genera embeddings para los chunks del documento.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector simple con una única posición activa.
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def fake_hybrid_embedding(self, texts: list[str], model_name: str | None = None) -> EmbeddingProviderResult:
    """
    Sustituye el proveedor externo por vectores controlados.

    Regla:
    - textos sobre gatos/felinos -> dimensión 0
    - textos sobre auditoría/normativa -> dimensión 1
    - resto -> dimensión 2
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "gato" in normalized_text or "felino" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "auditoría" in normalized_text or "normativa" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def test_p51_1_hybrid_search_combines_semantic_and_textual_results(monkeypatch):
    """
    P51.1 - Prueba de búsqueda híbrida.

    Verifica que:
    1. La consulta usa embedding para búsqueda semántica.
    2. La consulta usa texto literal para búsqueda textual.
    3. El resultado que coincide por ambas vías queda primero.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_hybrid_embedding,
    )

    reset_database_for_r51()

    create_user_with_role(
        email="r51@test.com",
        password="editor123",
        display_name="Usuario R51",
        role_name="editor",
    )

    token = login_and_get_token(
        email="r51@test.com",
        password="editor123",
    )

    audit_document = upload_text_document(
        token=token,
        title="Manual de auditoría",
        content=(
            "La auditoría documental revisa normativa interna, controles y evidencias. "
            "Este documento explica cómo conservar registros verificables."
        ),
    )

    cats_document = upload_text_document(
        token=token,
        title="Guía de gatos",
        content=(
            "El gato doméstico es un felino tranquilo. "
            "Los gatos suelen descansar muchas horas."
        ),
    )

    for document in [audit_document, cats_document]:
        extract_text(
            token=token,
            document_id=document["id"],
            version_number=1,
        )
        chunk_text(
            token=token,
            document_id=document["id"],
            version_number=1,
        )
        generate_embeddings(
            token=token,
            document_id=document["id"],
            version_number=1,
        )

    response = client.post(
        "/query",
        json={
            "query": "auditoría normativa",
            "limit": 5,
            "metric": "cosine",
            "search_mode": "hybrid",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["message"] == "Consulta híbrida procesada correctamente"
    assert payload["debug"]["search_mode"] == "hybrid"
    assert payload["retrieved_chunks"] >= 1

    best_result = payload["results"][0]

    assert best_result["title"] == "Manual de auditoría"
    assert best_result["match_source"] == "semantic_textual"
    assert best_result["similarity_score"] == 1.0
    assert best_result["textual_score"] == 1.0
    assert best_result["hybrid_score"] == 2.0