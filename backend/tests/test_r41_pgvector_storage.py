from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import SessionLocal
from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.documents.models import DocumentEmbedding
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

# Cliente HTTP de pruebas para llamar a la API como si fuera un usuario real.
client = TestClient(app)

# Contexto para generar hashes de contraseña seguros.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r41() -> None:
    """
    Limpia la base de datos para que la prueba empiece
    desde un estado mínimo y controlado.
    """
    db = SessionLocal()

    try:
        # Borramos primero lo más dependiente.
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

        # Recreamos los roles base que necesita el proyecto.
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
    Crea un usuario de prueba y le asigna un rol del sistema.
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
    Crea un documento lógico basado en texto usando
    el endpoint de subida ya existente.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def extract_text(token: str, document_id: str, version_number: int) -> dict:
    """
    Ejecuta la extracción de texto para la versión indicada.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def chunk_text(token: str, document_id: str, version_number: int, chunk_size: int, chunk_overlap: int) -> dict:
    """
    Genera los chunks que luego se usarán en R41.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        params={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def generate_embeddings(token: str, document_id: str, version_number: int) -> dict:
    """
    Llama al endpoint ya existente de embeddings.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def test_p41_1_pgvector_storage(monkeypatch):
    """
    P41.1 - Prueba de almacenamiento vectorial.

    Verifica:
    - que los embeddings se generan correctamente
    - que se persisten en una columna real de tipo vector
    - que la dimensión guardada coincide con la esperada
    """

    def fake_generate_embeddings(self, texts: list[str], model_name: str | None = None) -> EmbeddingProviderResult:
        """
        Sustituto local del proveedor externo para no depender
        de red ni de una API key real en la prueba.
        """
        final_model_name = model_name or settings.openai_embeddings_model
        fake_vectors: list[list[float]] = []

        for index, text_value in enumerate(texts):
            # Creamos un vector de 1536 posiciones porque en R41
            # la columna pgvector queda fijada a esa dimensión.
            base_value = float(index + 1)
            vector = [base_value] * settings.openai_embeddings_dimensions

            # Metemos una pequeña variación en la primera posición
            # para que el vector no sea completamente trivial.
            vector[0] = float(len(text_value))

            fake_vectors.append(vector)

        return EmbeddingProviderResult(
            model_name=final_model_name,
            vectors=fake_vectors,
        )

    # Reemplazamos la llamada real a OpenAI por una versión falsa controlada.
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    reset_database_for_r41()

    create_user_with_role(
        email="r41@test.com",
        password="editor123",
        display_name="Usuario R41",
        role_name="editor",
    )

    token = login_and_get_token(
        email="r41@test.com",
        password="editor123",
    )

    uploaded_document = upload_text_document(
        token=token,
        title="Documento R41",
        content=(
            "Este documento sirve para comprobar que el almacenamiento "
            "de embeddings ya no se hace como JSON normal, sino en una "
            "columna real de tipo vector dentro de PostgreSQL con pgvector. "
            "Necesitamos varios fragmentos para validar la persistencia."
        ),
    )

    document_id = uploaded_document["id"]
    version_number = 1

    extracted_response = extract_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )

    assert extracted_response["extraction_status"] == "completed"
    assert extracted_response["characters_count"] > 0

    chunk_response = chunk_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
        chunk_size=80,
        chunk_overlap=20,
    )

    assert chunk_response["total_chunks"] >= 2

    embeddings_response = generate_embeddings(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )

    assert embeddings_response["document_id"] == document_id
    assert embeddings_response["version_number"] == version_number
    assert embeddings_response["total_embeddings"] == chunk_response["total_chunks"]

    for item in embeddings_response["items"]:
        assert item["model_name"] == settings.openai_embeddings_model
        assert item["provider"] == "openai"
        assert item["dimensions"] == settings.openai_embeddings_dimensions

    db = SessionLocal()

    try:
        persisted_embeddings = list(
            db.execute(
                select(DocumentEmbedding).where(
                    DocumentEmbedding.document_id == document_id
                )
            ).scalars().all()
        )

        assert len(persisted_embeddings) == chunk_response["total_chunks"]

        for embedding in persisted_embeddings:
            assert embedding.model_name == settings.openai_embeddings_model
            assert embedding.provider == "openai"
            assert embedding.dimensions == settings.openai_embeddings_dimensions

            # pgvector suele devolver numpy.ndarray al leer desde la BD,
            # no necesariamente una lista Python.
            assert embedding.embedding_vector is not None

            vector_as_list = embedding.embedding_vector.tolist()
            assert isinstance(vector_as_list, list)
            assert len(vector_as_list) == settings.openai_embeddings_dimensions

        raw_row = db.execute(
            text(
                """
                SELECT
                    pg_typeof(embedding_vector)::text AS vector_type,
                    vector_dims(embedding_vector) AS vector_dims
                FROM document_embeddings
                LIMIT 1
                """
            )
        ).mappings().first()

        assert raw_row is not None
        assert raw_row["vector_type"] == "vector"
        assert raw_row["vector_dims"] == settings.openai_embeddings_dimensions
    finally:
        db.close()