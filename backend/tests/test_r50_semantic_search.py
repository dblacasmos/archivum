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


def reset_database_for_r50() -> None:
    """
    Limpia la base de datos para dejar el escenario de prueba
    en un estado pequeño, controlado y repetible.
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
    Crea un usuario de prueba y le asigna un rol.
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
    Sube un documento textual al sistema.
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
    Ejecuta la extracción de texto sobre la versión indicada.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def chunk_text(token: str, document_id: str, version_number: int, chunk_size: int, chunk_overlap: int) -> None:
    """
    Genera chunks para la versión indicada.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        params={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def generate_embeddings(token: str, document_id: str, version_number: int) -> None:
    """
    Genera embeddings para los chunks ya creados.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector muy simple y controlado para saber
    qué documento debería recuperarse primero.
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def fake_semantic_embedding(self, texts: list[str], model_name: str | None = None) -> EmbeddingProviderResult:
    """
    Sustituye la llamada real al proveedor externo por vectores
    deterministas y fáciles de verificar.

    Regla sencilla:
    - textos sobre gatos/felinos -> dimensión 0
    - textos sobre perros/caninos -> dimensión 1
    - resto -> dimensión 2
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "gato" in normalized_text or "felino" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "perro" in normalized_text or "canino" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def test_p50_1_semantic_search_returns_most_similar_chunks(monkeypatch):
    """
    P50.1 - Prueba de búsqueda semántica.

    Verifica que:
    1. La consulta genera un embedding.
    2. La búsqueda vectorial se ejecuta sobre los embeddings almacenados.
    3. El primer resultado recuperado es el chunk semánticamente esperado.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_semantic_embedding,
    )

    reset_database_for_r50()

    create_user_with_role(
        email="r50@test.com",
        password="editor123",
        display_name="Usuario R50",
        role_name="editor",
    )

    token = login_and_get_token(
        email="r50@test.com",
        password="editor123",
    )

    cats_document = upload_text_document(
        token=token,
        title="Guía de gatos",
        content=(
            "El gato doméstico es un felino tranquilo y ágil. "
            "Los gatos suelen descansar muchas horas y tienen comportamiento territorial."
        ),
    )

    dogs_document = upload_text_document(
        token=token,
        title="Guía de perros",
        content=(
            "El perro doméstico es un canino social y activo. "
            "Los perros suelen responder bien al adiestramiento y al ejercicio."
        ),
    )

    for document in [cats_document, dogs_document]:
        extract_text(
            token=token,
            document_id=document["id"],
            version_number=1,
        )
        chunk_text(
            token=token,
            document_id=document["id"],
            version_number=1,
            chunk_size=200,
            chunk_overlap=0,
        )
        generate_embeddings(
            token=token,
            document_id=document["id"],
            version_number=1,
        )

    response = client.post(
        "/query",
        json={
            "query": "información sobre gatos felinos",
            "limit": 3,
            "metric": "cosine",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["message"] == "Consulta semántica procesada correctamente"
    assert payload["retrieved_chunks"] >= 1
    assert len(payload["results"]) >= 1

    best_result = payload["results"][0]

    assert best_result["title"] == "Guía de gatos"
    assert best_result["chunk_index"] == 0
    assert best_result["distance_value"] == 0.0
    assert best_result["similarity_score"] == 1.0