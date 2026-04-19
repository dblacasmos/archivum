import uuid

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.documents.repository import DocumentRepository
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

# Cliente HTTP para probar la API como si fuera un usuario real.
client = TestClient(app)

# Utilidad para generar hashes de contraseña en usuarios de prueba.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r42() -> None:
    """
    Limpia la base de datos para dejar el escenario de prueba
    en un estado pequeño, controlado y repetible.
    """
    db = SessionLocal()

    try:
        # Borramos primero lo más dependiente para evitar
        # errores de claves foráneas al limpiar tablas.
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


def extract_text(token: str, document_id: str, version_number: int) -> dict:
    """
    Ejecuta la extracción de texto sobre la versión indicada.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/extract-text",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def chunk_text(token: str, document_id: str, version_number: int, chunk_size: int, chunk_overlap: int) -> dict:
    """
    Genera los chunks de la versión indicada.
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
    Genera embeddings para los chunks ya creados.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector muy simple y controlado para que la prueba
    sepa exactamente cuál debería ser el resultado más parecido.

    Ejemplo:
    - chunk 0 -> vector con valor fuerte en posición 0
    - chunk 1 -> vector con valor fuerte en posición 1
    - chunk 2 -> vector con valor fuerte en posición 2
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def test_p42_1_vector_index_and_similarity_query(monkeypatch):
    """
    P42.1 - Prueba de consulta vectorial.

    Verifica tres cosas:
    1. El índice vectorial existe en PostgreSQL.
    2. Está configurado con ivfflat y cosine ops.
    3. Una consulta vectorial real devuelve primero el chunk esperado.
    """

    def fake_generate_embeddings(self, texts: list[str], model_name: str | None = None) -> EmbeddingProviderResult:
        """
        Sustituye la llamada real al proveedor externo por vectores
        deterministas y totalmente controlados para la prueba.
        """
        final_model_name = model_name or settings.openai_embeddings_model
        fake_vectors: list[list[float]] = []

        for index, _text_value in enumerate(texts):
            fake_vectors.append(build_sparse_vector(index))

        return EmbeddingProviderResult(
            model_name=final_model_name,
            vectors=fake_vectors,
        )

    # Sustituimos temporalmente el cliente real por uno falso.
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    reset_database_for_r42()

    create_user_with_role(
        email="r42@test.com",
        password="editor123",
        display_name="Usuario R42",
        role_name="editor",
    )

    token = login_and_get_token(
        email="r42@test.com",
        password="editor123",
    )

    uploaded_document = upload_text_document(
        token=token,
        title="Documento R42",
        content=(
            "Bloque uno del documento para crear el primer chunk. "
            "Bloque dos del documento para crear el segundo chunk. "
            "Bloque tres del documento para crear el tercer chunk. "
            "Bloque cuatro para asegurar suficiente longitud total."
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

    chunk_response = chunk_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
        chunk_size=45,
        chunk_overlap=0,
    )

    assert chunk_response["total_chunks"] >= 3

    embeddings_response = generate_embeddings(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )

    assert embeddings_response["total_embeddings"] == chunk_response["total_chunks"]

    db = SessionLocal()

    try:
        document_repo = DocumentRepository(db)
        embedding_repo = DocumentEmbeddingRepository(db)

        version = document_repo.get_document_version(
            document_id=uuid.UUID(document_id),
            version_number=version_number,
        )
        assert version is not None

        # Usamos como consulta el mismo vector del chunk 0.
        # Si la búsqueda funciona, el primer resultado debe ser ese chunk.
        query_vector = build_sparse_vector(0)

        similarity_results = embedding_repo.similarity_search_by_vector(
            document_version_id=version.id,
            query_vector=query_vector,
            limit=3,
            metric="cosine",
        )

        assert len(similarity_results) >= 1
        assert similarity_results[0]["chunk_index"] == 0
        assert float(similarity_results[0]["distance_value"]) == 0.0

        # Comprobamos que el índice vectorial existe y está bien definido.
        index_row = db.execute(
            text(
                """
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'document_embeddings'
                  AND indexname = 'ix_document_embeddings_embedding_vector_cosine'
                """
            )
        ).mappings().first()

        assert index_row is not None
        assert "USING ivfflat" in index_row["indexdef"]
        assert "vector_cosine_ops" in index_row["indexdef"]

        # Ejecutamos EXPLAIN sobre una consulta puramente vectorial para
        # verificar que PostgreSQL puede apoyarse en el índice ivfflat
        # creado para R42.
        db.execute(text("SET enable_seqscan = off"))
        db.execute(text("SET enable_sort = off"))

        explain_rows = db.execute(
            text(
                """
                EXPLAIN
                SELECT
                    de.id
                FROM document_embeddings AS de
                ORDER BY de.embedding_vector <=> CAST(:query_vector AS vector)
                LIMIT 3
                """
            ),
            {
                "query_vector": "[" + ",".join(str(value) for value in query_vector) + "]",
            },
        ).fetchall()

        explain_plan = "\n".join(row[0] for row in explain_rows)

        assert (
            "ix_document_embeddings_embedding_vector_cosine" in explain_plan
            or "Index Scan using ix_document_embeddings_embedding_vector_cosine" in explain_plan
        )
    finally:
        db.close()