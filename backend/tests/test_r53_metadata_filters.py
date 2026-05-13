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


def reset_database_for_r53() -> None:
    """
    Limpia la base de datos para que las pruebas de R53 sean repetibles.

    Así evitamos que documentos, metadata o embeddings de otros tests
    contaminen el resultado. Qué concepto tan revolucionario: limpiar antes de probar.
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
) -> None:
    """
    Crea un usuario de prueba con el rol indicado.
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


def login_and_get_token(
    email: str,
    password: str,
) -> str:
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


def upload_text_document(
    token: str,
    title: str,
    content: str,
) -> dict:
    """
    Sube un documento textual usando el endpoint real del sistema.
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
) -> dict:
    """
    Añade o actualiza una metadata del documento.
    """
    response = client.post(
        f"/documents/{document_id}/metadata",
        json={
            "key": key,
            "value": value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def extract_text(
    token: str,
    document_id: str,
    version_number: int,
) -> None:
    """
    Ejecuta la extracción de texto sobre una versión documental.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def chunk_text(
    token: str,
    document_id: str,
    version_number: int,
) -> None:
    """
    Genera chunks grandes para que cada documento tenga un fragmento principal.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        params={"chunk_size": 300, "chunk_overlap": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def generate_embeddings(
    token: str,
    document_id: str,
    version_number: int,
) -> None:
    """
    Genera embeddings para los chunks de un documento.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector simple con una única posición activa.

    Sirve para controlar artificialmente qué documentos son parecidos
    sin depender de OpenAI.
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def fake_metadata_filter_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Sustituye OpenAI por vectores controlados.

    Regla:
    - textos sobre contratos/legal -> dimensión 0
    - textos sobre auditoría/normativa -> dimensión 1
    - resto -> dimensión 2
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "contrato" in normalized_text or "legal" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "auditoría" in normalized_text or "normativa" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def prepare_r53_search_scenario(token: str) -> tuple[dict, dict]:
    """
    Crea dos documentos con metadata distinta y los deja listos para búsqueda.

    Documento 1:
    - category = legal

    Documento 2:
    - category = auditoria
    """
    legal_document = upload_text_document(
        token=token,
        title="Contrato legal",
        content=(
            "El contrato legal recoge obligaciones, cláusulas y condiciones. "
            "Este documento pertenece al área jurídica."
        ),
    )

    audit_document = upload_text_document(
        token=token,
        title="Manual de auditoría",
        content=(
            "La auditoría documental revisa normativa interna, controles y evidencias. "
            "Este documento pertenece al área de cumplimiento."
        ),
    )

    add_document_metadata(
        token=token,
        document_id=legal_document["id"],
        key="category",
        value="legal",
    )

    add_document_metadata(
        token=token,
        document_id=audit_document["id"],
        key="category",
        value="auditoria",
    )

    for document in [legal_document, audit_document]:
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

    return legal_document, audit_document


def test_r53_filters_reduce_results(monkeypatch):
    """
    P53.1 - Verifica que el filtro por metadata reduce los resultados.

    La búsqueda sin filtro puede devolver varios documentos.
    La búsqueda con category=legal debe devolver solo documentos legales.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_metadata_filter_embedding,
    )

    reset_database_for_r53()

    create_user_with_role(
        email="r53@test.com",
        password="editor123",
        display_name="Usuario R53",
        role_name="editor",
    )

    token = login_and_get_token(
        email="r53@test.com",
        password="editor123",
    )

    prepare_r53_search_scenario(token=token)

    response_no_filter = client.post(
        "/query",
        json={
            "query": "contrato legal",
            "limit": 10,
            "metric": "cosine",
            "search_mode": "hybrid",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response_no_filter.status_code == 200, response_no_filter.text

    response_filtered = client.post(
        "/query",
        json={
            "query": "contrato legal",
            "limit": 10,
            "metric": "cosine",
            "search_mode": "hybrid",
            "metadata_filters": {
                "category": "legal",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response_filtered.status_code == 200, response_filtered.text

    data_no_filter = response_no_filter.json()
    data_filtered = response_filtered.json()

    assert data_no_filter["retrieved_chunks"] >= data_filtered["retrieved_chunks"]
    assert data_filtered["retrieved_chunks"] >= 1
    assert data_filtered["debug"]["metadata_filters"] == {"category": "legal"}

    for result in data_filtered["results"]:
        assert result["title"] == "Contrato legal"


def test_r53_filters_no_results(monkeypatch):
    """
    P53.1 - Verifica que un filtro sin coincidencias devuelve lista vacía.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_metadata_filter_embedding,
    )

    reset_database_for_r53()

    create_user_with_role(
        email="r53_empty@test.com",
        password="editor123",
        display_name="Usuario R53 Sin Resultados",
        role_name="editor",
    )

    token = login_and_get_token(
        email="r53_empty@test.com",
        password="editor123",
    )

    prepare_r53_search_scenario(token=token)

    response = client.post(
        "/query",
        json={
            "query": "contrato legal",
            "limit": 10,
            "metric": "cosine",
            "search_mode": "hybrid",
            "metadata_filters": {
                "category": "inexistente",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["retrieved_chunks"] == 0
    assert data["results"] == []
    assert data["debug"]["metadata_filters"] == {"category": "inexistente"}