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

# Cliente HTTP de pruebas para simular llamadas reales a la API.
client = TestClient(app)

# Utilidad para generar hashes de contraseña en usuarios de prueba.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r40() -> None:
    """
    Limpia las tablas necesarias para dejar la base
    en un estado limpio antes de ejecutar la prueba.
    """
    db = SessionLocal()

    try:
        # Borramos tablas dependientes primero.
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

        # Recreamos roles base del sistema.
        db.execute(
            text(
                """
                INSERT INTO roles (id, name, description) VALUES
                (gen_random_uuid(), 'admin', 'Administrador del sistema'),
                (gen_random_uuid(), 'editor', 'Puede crear y gestionar documentos'),
                (gen_random_uuid(), 'viewer', 'Puede consultar documentos');
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
        assert role is not None, f"No existe el rol {role_name}"

        user_repo.assign_role(user, role)

    finally:
        db.close()


def login_and_get_token(email: str, password: str) -> str:
    """
    Hace login y devuelve el token JWT.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()
    return data["access_token"]


def upload_text_document(token: str, title: str, content: str) -> dict:
    """
    Sube un documento de texto usando el endpoint real.
    """
    response = client.post(
        "/documents/upload",
        data={
            "title": title,
            "content": content,
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def extract_text(
    token: str,
    document_id: str,
    version_number: int,
) -> dict:
    """
    Ejecuta la extracción de texto del documento.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    return response.json()


def chunk_text(
    token: str,
    document_id: str,
    version_number: int,
    chunk_size: int,
    chunk_overlap: int,
) -> dict:
    """
    Ejecuta el chunking para generar fragmentos.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/chunk-text",
        params={
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    return response.json()


def generate_embeddings(
    token: str,
    document_id: str,
    version_number: int,
) -> dict:
    """
    Llama al endpoint real de embeddings.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def test_p40_1_generate_embeddings(monkeypatch):
    """
    P40.1 - Verifica la generación y persistencia
    de embeddings asociados a los chunks.
    """

    def fake_generate_embeddings(
        self,
        texts: list[str],
        model_name: str | None = None,
    ) -> EmbeddingProviderResult:
        """
        Sustituye la llamada real a OpenAI por datos falsos
        controlados para pruebas automáticas.
        """
        final_model_name = model_name or settings.openai_embeddings_model

        fake_vectors: list[list[float]] = []

        for index, text_value in enumerate(texts):
            # Creamos un vector compatible con pgvector:
            # 1536 dimensiones.
            vector = [float(index + 1)] * settings.openai_embeddings_dimensions

            # Alteramos la primera posición para que no todos
            # los vectores sean idénticos.
            vector[0] = float(len(text_value))

            fake_vectors.append(vector)

        return EmbeddingProviderResult(
            model_name=final_model_name,
            vectors=fake_vectors,
        )

    # Reemplazamos temporalmente la llamada real.
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    # Reiniciamos entorno de prueba.
    reset_database_for_r40()

    # Creamos usuario editor.
    create_user_with_role(
        email="r40@test.com",
        password="editor123",
        display_name="Usuario R40",
        role_name="editor",
    )

    # Login real.
    token = login_and_get_token(
        email="r40@test.com",
        password="editor123",
    )

    # Subimos documento.
    uploaded_document = upload_text_document(
        token=token,
        title="Documento Embeddings R40",
        content=(
            "Este documento sirve para probar la generación "
            "de embeddings dentro del requisito R40. "
            "Necesitamos suficiente texto para que el sistema "
            "genere varios chunks y luego vectores asociados."
        ),
    )

    document_id = uploaded_document["id"]
    version_number = 1

    # Extraemos texto.
    extraction_response = extract_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )

    assert extraction_response["extraction_status"] == "completed"
    assert extraction_response["characters_count"] > 0

    # Generamos chunks.
    chunk_response = chunk_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
        chunk_size=80,
        chunk_overlap=20,
    )

    assert chunk_response["total_chunks"] >= 2

    # Generamos embeddings.
    embeddings_response = generate_embeddings(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )

    # Validamos respuesta API.
    assert embeddings_response["document_id"] == document_id
    assert embeddings_response["version_number"] == version_number
    assert embeddings_response["total_embeddings"] == chunk_response["total_chunks"]

    for item in embeddings_response["items"]:
        assert item["model_name"] == settings.openai_embeddings_model
        assert item["provider"] == "openai"
        assert item["dimensions"] == settings.openai_embeddings_dimensions

    # Revisamos persistencia real en base de datos.
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

            assert embedding.chunk_id is not None

    finally:
        db.close()