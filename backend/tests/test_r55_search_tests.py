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


def reset_database_for_r55() -> None:
    """
    Limpia la base de datos para que los tests de R55 sean repetibles.

    R55 valida el bloque completo de búsqueda, así que necesitamos empezar
    sin documentos, chunks, embeddings ni usuarios de pruebas anteriores.
    Si no, pytest se convierte en una tómbola con stacktrace.
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
    Crea un usuario de prueba con un rol y devuelve su identificador.
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
    Hace login con el endpoint real y devuelve el access token.
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
    Crea un documento textual usando el endpoint real de subida.
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
    Añade metadata al documento para poder probar filtros en /query.
    """
    response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": key, "value": value},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


def extract_text(token: str, document_id: str) -> None:
    """
    Extrae el texto de la versión 1 del documento.
    """
    response = client.post(
        f"/documents/{document_id}/versions/1/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def chunk_text(token: str, document_id: str) -> None:
    """
    Divide el texto en chunks suficientemente grandes para controlar el escenario.
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


def share_document(token: str, document_id: str, target_user_id: str) -> None:
    """
    Comparte un documento con otro usuario usando la ACL simple del proyecto.
    """
    response = client.post(
        f"/documents/{document_id}/share",
        json={"user_id": target_user_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector artificial con una sola posición activa.

    Esto permite saber qué documento debería ganar la búsqueda sin llamar a OpenAI.
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def fake_r55_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Sustituye OpenAI por embeddings controlados para R55.

    Reglas:
    - contrato/legal/privado -> vector 0
    - auditoría/normativa -> vector 1
    - financiero/presupuesto -> vector 2
    - cualquier otro texto -> vector 3
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if (
            "contrato" in normalized_text
            or "legal" in normalized_text
            or "privado" in normalized_text
        ):
            fake_vectors.append(build_sparse_vector(0))
        elif "auditoría" in normalized_text or "normativa" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        elif "financiero" in normalized_text or "presupuesto" in normalized_text:
            fake_vectors.append(build_sparse_vector(2))
        else:
            fake_vectors.append(build_sparse_vector(3))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def prepare_document_for_search(
    token: str,
    title: str,
    content: str,
    metadata: dict[str, str],
) -> dict:
    """
    Crea un documento completo y lo deja preparado para aparecer en /query.
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


def prepare_r55_search_scenario(monkeypatch) -> dict:
    """
    Prepara un escenario realista para validar R50-R54 juntos.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r55_embedding,
    )

    reset_database_for_r55()

    alice_user_id = create_user_with_role(
        email="alice_r55@test.com",
        password="editor123",
        display_name="Alice R55",
        role_name="editor",
    )

    create_user_with_role(
        email="bob_r55@test.com",
        password="editor123",
        display_name="Bob R55",
        role_name="editor",
    )

    alice_token = login_and_get_token(
        email="alice_r55@test.com",
        password="editor123",
    )

    bob_token = login_and_get_token(
        email="bob_r55@test.com",
        password="editor123",
    )

    legal_document = prepare_document_for_search(
        token=alice_token,
        title="Contrato legal autorizado",
        content=(
            "Contrato legal autorizado con cláusulas de confidencialidad. "
            "Este fragmento legal debe aparecer para Alice."
        ),
        metadata={"category": "legal", "department": "juridico"},
    )

    audit_document = prepare_document_for_search(
        token=alice_token,
        title="Normativa de auditoría autorizada",
        content=(
            "Normativa de auditoría interna con controles y evidencias. "
            "Este fragmento debe aparecer solo al filtrar auditoría."
        ),
        metadata={"category": "auditoria", "department": "cumplimiento"},
    )

    private_document = prepare_document_for_search(
        token=bob_token,
        title="Contrato privado de Bob",
        content=(
            "Contrato privado de Bob con información legal confidencial. "
            "Alice no debe recuperar este fragmento jamás."
        ),
        metadata={"category": "legal", "department": "juridico"},
    )

    shared_document = prepare_document_for_search(
        token=bob_token,
        title="Presupuesto financiero compartido",
        content=(
            "Presupuesto financiero compartido con Alice para revisión. "
            "Este fragmento sí puede aparecer por permiso explícito."
        ),
        metadata={"category": "finanzas", "department": "financiero"},
    )

    share_document(
        token=bob_token,
        document_id=shared_document["id"],
        target_user_id=alice_user_id,
    )

    return {
        "alice_token": alice_token,
        "bob_token": bob_token,
        "legal_document": legal_document,
        "audit_document": audit_document,
        "private_document": private_document,
        "shared_document": shared_document,
    }


def search_documents(
    token: str,
    query: str,
    search_mode: str = "hybrid",
    metadata_filters: dict[str, str] | None = None,
    limit: int = 10,
) -> dict:
    """
    Ejecuta una consulta contra /query y devuelve el JSON de respuesta.
    """
    payload = {
        "query": query,
        "limit": limit,
        "metric": "cosine",
        "search_mode": search_mode,
    }

    if metadata_filters is not None:
        payload["metadata_filters"] = metadata_filters

    response = client.post(
        "/query",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def test_r55_end_to_end_hybrid_query_with_ranking_and_active_filters(monkeypatch):
    """
    P55.1 - Consulta híbrida end-to-end con ranking y filtros activos.
    """
    scenario = prepare_r55_search_scenario(monkeypatch)

    data = search_documents(
        token=scenario["alice_token"],
        query="contrato legal autorizado",
        search_mode="hybrid",
        metadata_filters={"category": "legal"},
    )

    assert data["message"] == "Consulta híbrida procesada correctamente"
    assert data["debug"]["search_mode"] == "hybrid"
    assert data["debug"]["metadata_filters"] == {"category": "legal"}
    assert data["retrieved_chunks"] >= 1

    first_result = data["results"][0]

    assert first_result["document_id"] == scenario["legal_document"]["id"]
    assert first_result["match_source"] == "semantic_textual"
    assert first_result["ranking_position"] == 1
    assert first_result["ranking_score"] is not None
    assert first_result["relevance_label"] in {"alta", "media", "baja"}
    assert first_result["relevance_explanation"]
    assert first_result["ranking_factors"] is not None


def test_r55_combined_ranking_metadata_and_security_validation(monkeypatch):
    """
    P55.2 - Valida ranking + metadata + seguridad trabajando a la vez.
    """
    scenario = prepare_r55_search_scenario(monkeypatch)

    data = search_documents(
        token=scenario["alice_token"],
        query="presupuesto financiero compartido",
        search_mode="hybrid",
        metadata_filters={"category": "finanzas"},
    )

    result_document_ids = {result["document_id"] for result in data["results"]}

    assert scenario["shared_document"]["id"] in result_document_ids
    assert scenario["legal_document"]["id"] not in result_document_ids
    assert scenario["audit_document"]["id"] not in result_document_ids
    assert scenario["private_document"]["id"] not in result_document_ids

    assert data["results"][0]["document_id"] == scenario["shared_document"]["id"]
    assert data["results"][0]["ranking_position"] == 1
    assert data["results"][0]["ranking_score"] is not None


def test_r55_excludes_unauthorized_results_in_real_retrieval_scenario(monkeypatch):
    """
    P55.3 - Verifica exclusión de resultados no autorizados.
    """
    scenario = prepare_r55_search_scenario(monkeypatch)

    data = search_documents(
        token=scenario["alice_token"],
        query="contrato privado de Bob",
        search_mode="hybrid",
    )

    result_document_ids = {result["document_id"] for result in data["results"]}

    assert scenario["private_document"]["id"] not in result_document_ids
    assert all(
        result["document_id"] != scenario["private_document"]["id"]
        for result in data["results"]
    )


def test_r55_compares_authorized_and_unauthorized_results_in_real_scenario(monkeypatch):
    """
    P55.4 - Compara resultados autorizados y no autorizados en escenario real.
    """
    scenario = prepare_r55_search_scenario(monkeypatch)

    alice_data = search_documents(
        token=scenario["alice_token"],
        query="contrato privado de Bob",
        search_mode="hybrid",
    )

    bob_data = search_documents(
        token=scenario["bob_token"],
        query="contrato privado de Bob",
        search_mode="hybrid",
    )

    alice_document_ids = {result["document_id"] for result in alice_data["results"]}
    bob_document_ids = {result["document_id"] for result in bob_data["results"]}

    assert scenario["private_document"]["id"] not in alice_document_ids
    assert scenario["private_document"]["id"] in bob_document_ids

    bob_private_result = next(
        result
        for result in bob_data["results"]
        if result["document_id"] == scenario["private_document"]["id"]
    )

    assert bob_private_result["ranking_position"] == 1
    assert bob_private_result["match_source"] == "semantic_textual"