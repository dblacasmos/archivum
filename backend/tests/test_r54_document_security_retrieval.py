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


def reset_database_for_r54() -> None:
    """
    Limpia la base de datos para que las pruebas de R54 sean repetibles.

    Si no limpiamos, un documento de otra prueba podría aparecer aquí
    y entonces el test sería una ruleta rusa con pytest, precioso desastre.
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
    Crea un usuario de prueba con un rol concreto y devuelve su ID.
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
    Crea un documento textual usando el endpoint real.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def extract_text(token: str, document_id: str) -> None:
    """
    Ejecuta la extracción de texto de la versión 1.
    """
    response = client.post(
        f"/documents/{document_id}/versions/1/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def chunk_text(token: str, document_id: str) -> None:
    """
    Genera chunks del documento para que puedan buscarse después.
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
    Crea un vector simple con una única posición activa.

    Así controlamos qué documento debería ser más parecido
    sin depender de OpenAI ni de magia cara con factura mensual.
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def fake_r54_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Sustituye OpenAI por embeddings controlados para el test.

    Regla:
    - textos con alpha/secreto -> vector 0
    - textos con beta/compartido -> vector 1
    - resto -> vector 2
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "alpha" in normalized_text or "secreto" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "beta" in normalized_text or "compartido" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def prepare_document_for_search(token: str, title: str, content: str) -> dict:
    """
    Crea un documento y ejecuta las fases mínimas para que aparezca en /query.
    """
    document = upload_text_document(
        token=token,
        title=title,
        content=content,
    )

    extract_text(token=token, document_id=document["id"])
    chunk_text(token=token, document_id=document["id"])
    generate_embeddings(token=token, document_id=document["id"])

    return document


def share_document(token: str, document_id: str, target_user_id: str) -> None:
    """
    Comparte un documento con otro usuario usando la ACL simple de R12.
    """
    response = client.post(
        f"/documents/{document_id}/share",
        json={"user_id": target_user_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def test_r54_retrieval_excludes_documents_from_other_owner(monkeypatch):
    """
    P54.1 / P54.2 - Un usuario no recupera documentos de otro owner.

    Aunque la consulta encaje con contenido ajeno, el filtro de seguridad
    debe excluir ese documento antes del ranking.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r54_embedding,
    )

    reset_database_for_r54()

    create_user_with_role(
        email="alice_r54@test.com",
        password="editor123",
        display_name="Alice R54",
        role_name="editor",
    )

    create_user_with_role(
        email="bob_r54@test.com",
        password="editor123",
        display_name="Bob R54",
        role_name="editor",
    )

    alice_token = login_and_get_token(
        email="alice_r54@test.com",
        password="editor123",
    )

    bob_token = login_and_get_token(
        email="bob_r54@test.com",
        password="editor123",
    )

    alice_document = prepare_document_for_search(
        token=alice_token,
        title="Documento alpha de Alice",
        content="Contenido alpha permitido para Alice.",
    )

    bob_document = prepare_document_for_search(
        token=bob_token,
        title="Documento secreto de Bob",
        content="Contenido secreto de Bob que Alice no debe recuperar.",
    )

    response = client.post(
        "/query",
        json={
            "query": "secreto de Bob",
            "limit": 10,
            "metric": "cosine",
            "search_mode": "hybrid",
        },
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()
    result_document_ids = {result["document_id"] for result in data["results"]}

    assert bob_document["id"] not in result_document_ids
    assert all(result["document_id"] == alice_document["id"] for result in data["results"])


def test_r54_retrieval_allows_shared_document_by_acl(monkeypatch):
    """
    P54.1 - Un usuario sí recupera un documento compartido por ACL.

    Esto valida que R54 no rompe R12:
    no solo cuenta el owner, también cuentan los permisos explícitos.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r54_embedding,
    )

    reset_database_for_r54()

    alice_user_id = create_user_with_role(
        email="alice_acl_r54@test.com",
        password="editor123",
        display_name="Alice ACL R54",
        role_name="editor",
    )

    create_user_with_role(
        email="bob_acl_r54@test.com",
        password="editor123",
        display_name="Bob ACL R54",
        role_name="editor",
    )

    alice_token = login_and_get_token(
        email="alice_acl_r54@test.com",
        password="editor123",
    )

    bob_token = login_and_get_token(
        email="bob_acl_r54@test.com",
        password="editor123",
    )

    shared_document = prepare_document_for_search(
        token=bob_token,
        title="Documento beta compartido",
        content="Contenido beta compartido con Alice mediante permisos ACL.",
    )

    share_document(
        token=bob_token,
        document_id=shared_document["id"],
        target_user_id=alice_user_id,
    )

    response = client.post(
        "/query",
        json={
            "query": "beta compartido",
            "limit": 10,
            "metric": "cosine",
            "search_mode": "hybrid",
        },
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()
    result_document_ids = {result["document_id"] for result in data["results"]}

    assert shared_document["id"] in result_document_ids