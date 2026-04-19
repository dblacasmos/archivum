import uuid

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import SessionLocal
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.documents.models import DocumentChunk, DocumentEmbedding
from app.documents.repository import DocumentRepository
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

# Cliente HTTP de pruebas para llamar a la API como si fuera un usuario real.
client = TestClient(app)

# Utilidad para generar hashes de contraseña en los usuarios de prueba.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def reset_database_for_r43() -> None:
    """
    Limpia las tablas necesarias para que cada test de R43
    empiece desde un estado pequeño, controlado y repetible.
    """
    db = SessionLocal()

    try:
        # Borramos primero las tablas más dependientes para no romper
        # claves foráneas al limpiar la base de datos.
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

        # Recreamos los roles base que necesita el sistema para que
        # el usuario de prueba pueda autenticarse y subir documentos.
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
    Crea un usuario de prueba y le asigna el rol indicado.
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
    Hace login contra la API real y devuelve el access token.
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
    return response.json()["access_token"]


def upload_text_document(token: str, title: str, content: str) -> dict:
    """
    Sube un documento textual para arrancar el flujo completo.
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


def extract_text(token: str, document_id: str, version_number: int) -> dict:
    """
    Ejecuta la extracción de texto sobre la versión indicada.
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
    Ejecuta el chunking para generar los fragmentos persistidos.
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


def generate_embeddings(token: str, document_id: str, version_number: int) -> dict:
    """
    Genera embeddings sobre los chunks ya creados.
    """
    response = client.post(
        f"/documents/{document_id}/versions/{version_number}/embeddings",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def build_sparse_vector(active_position: int) -> list[float]:
    """
    Crea un vector muy controlado para saber con certeza qué chunk
    debería ser el más parecido en la búsqueda vectorial.

    Ejemplo:
    - chunk 0 -> vector con un 1.0 en la posición 0
    - chunk 1 -> vector con un 1.0 en la posición 1
    - chunk 2 -> vector con un 1.0 en la posición 2
    """
    vector = [0.0] * settings.openai_embeddings_dimensions
    vector[active_position] = 1.0
    return vector


def prepare_vectorized_scenario(monkeypatch) -> dict:
    """
    Monta un escenario completo y reutilizable para los tests de R43:

    1. Crea usuario editor.
    2. Hace login.
    3. Sube un documento.
    4. Extrae el texto.
    5. Genera chunks.
    6. Genera embeddings falsos y deterministas.
    7. Devuelve los datos necesarios para las comprobaciones.
    """

    def fake_generate_embeddings(
        self,
        texts: list[str],
        model_name: str | None = None,
    ) -> EmbeddingProviderResult:
        """
        Sustituye temporalmente la llamada real al proveedor externo
        por vectores falsos, estables y fáciles de comprobar.
        """
        final_model_name = model_name or settings.openai_embeddings_model
        fake_vectors: list[list[float]] = []

        for index, _text_value in enumerate(texts):
            fake_vectors.append(build_sparse_vector(index))

        return EmbeddingProviderResult(
            model_name=final_model_name,
            vectors=fake_vectors,
        )

    # Reemplazamos el cliente real de OpenAI solo durante este test.
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    # Dejamos la base limpia antes de construir el escenario.
    reset_database_for_r43()

    # Creamos un usuario editor porque ese rol sí puede subir documentos
    # y ejecutar el flujo que estamos validando.
    create_user_with_role(
        email="r43@test.com",
        password="editor123",
        display_name="Usuario R43",
        role_name="editor",
    )

    # Hacemos login para trabajar contra la API protegida.
    token = login_and_get_token(
        email="r43@test.com",
        password="editor123",
    )

    # Subimos un documento suficientemente largo para forzar varios chunks.
    uploaded_document = upload_text_document(
        token=token,
        title="Documento de prueba R43",
        content=(
            "Primer bloque del documento para generar el chunk uno. "
            "Segundo bloque del documento para generar el chunk dos. "
            "Tercer bloque del documento para generar el chunk tres. "
            "Cuarto bloque del documento para asegurar suficiente longitud. "
            "Quinto bloque adicional para que la prueba tenga margen estable."
        ),
    )

    document_id = uploaded_document["id"]
    version_number = 1

    # Lanzamos la extracción de texto real.
    extracted_response = extract_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )
    assert extracted_response["extraction_status"] == "completed"

    # Fragmentamos el texto en varios trozos pequeños y ordenados.
    chunk_response = chunk_text(
        token=token,
        document_id=document_id,
        version_number=version_number,
        chunk_size=45,
        chunk_overlap=0,
    )
    assert chunk_response["total_chunks"] >= 3

    # Generamos embeddings usando los vectores falsos definidos arriba.
    embeddings_response = generate_embeddings(
        token=token,
        document_id=document_id,
        version_number=version_number,
    )
    assert embeddings_response["total_embeddings"] == chunk_response["total_chunks"]

    # Abrimos sesión de base de datos para validar persistencia real.
    db = SessionLocal()

    try:
        document_repo = DocumentRepository(db)
        embedding_repo = DocumentEmbeddingRepository(db)

        version = document_repo.get_document_version(
            document_id=uuid.UUID(document_id),
            version_number=version_number,
        )
        assert version is not None

        chunks = list(
            db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_version_id == version.id)
                .order_by(DocumentChunk.chunk_index.asc())
            ).scalars().all()
        )

        embeddings = list(
            db.execute(
                select(DocumentEmbedding)
                .where(DocumentEmbedding.document_version_id == version.id)
                .order_by(DocumentEmbedding.created_at.asc())
            ).scalars().all()
        )

        return {
            "db": db,
            "document_id": document_id,
            "version_number": version_number,
            "version_id": version.id,
            "chunks": chunks,
            "embeddings": embeddings,
            "embedding_repo": embedding_repo,
        }
    except Exception:
        db.close()
        raise


def test_p43_1_end_to_end_vector_flow(monkeypatch):
    """
    P43.1 - Prueba end-to-end:
    chunk -> embedding -> persistencia en pgvector -> recuperación por similitud.
    """
    scenario = prepare_vectorized_scenario(monkeypatch)
    db = scenario["db"]

    try:
        chunks = scenario["chunks"]
        embeddings = scenario["embeddings"]
        embedding_repo = scenario["embedding_repo"]

        # Comprobamos que realmente hay chunks y embeddings guardados.
        assert len(chunks) >= 3
        assert len(embeddings) == len(chunks)

        # Verificamos que el vector quedó guardado con la dimensión esperada.
        assert embeddings[0].dimensions == settings.openai_embeddings_dimensions
        assert len(embeddings[0].embedding_vector) == settings.openai_embeddings_dimensions

        # Lanzamos una búsqueda por similitud usando el vector del chunk 1.
        query_vector = build_sparse_vector(1)

        similarity_results = embedding_repo.similarity_search_by_vector(
            document_version_id=scenario["version_id"],
            query_vector=query_vector,
            limit=3,
            metric="cosine",
        )

        # La consulta debe devolver resultados y el primero debe ser el chunk 1.
        assert len(similarity_results) >= 1
        assert similarity_results[0]["chunk_index"] == 1
        assert float(similarity_results[0]["distance_value"]) == 0.0
    finally:
        db.close()


def test_p43_2_retrieved_embedding_matches_expected_chunk(monkeypatch):
    """
    P43.2 - Verificación de coherencia:
    el embedding recuperado corresponde al chunk esperado.
    """
    scenario = prepare_vectorized_scenario(monkeypatch)
    db = scenario["db"]

    try:
        chunks = scenario["chunks"]
        embedding_repo = scenario["embedding_repo"]

        # Elegimos el tercer chunk para no probar siempre el primero
        # y así comprobar mejor la coherencia real de la recuperación.
        expected_chunk = chunks[2]

        query_vector = build_sparse_vector(expected_chunk.chunk_index)

        similarity_results = embedding_repo.similarity_search_by_vector(
            document_version_id=scenario["version_id"],
            query_vector=query_vector,
            limit=1,
            metric="cosine",
        )

        assert len(similarity_results) == 1

        best_result = similarity_results[0]

        # Validamos que el resultado devuelto por la búsqueda vectorial
        # coincide exactamente con el chunk que esperábamos recuperar.
        assert str(best_result["chunk_id"]) == str(expected_chunk.id)
        assert best_result["chunk_index"] == expected_chunk.chunk_index
        assert best_result["chunk_content"] == expected_chunk.content
        assert float(best_result["distance_value"]) == 0.0
    finally:
        db.close()


def test_p43_3_vector_index_is_operational(monkeypatch):
    """
    P43.3 - Validación de índice:
    la consulta vectorial es operativa y PostgreSQL puede apoyarse
    en el índice configurado sobre la columna embedding_vector.
    """
    scenario = prepare_vectorized_scenario(monkeypatch)
    db = scenario["db"]

    try:
        query_vector = build_sparse_vector(0)

        # Comprobamos que el índice esperado existe en PostgreSQL
        # y que está creado con ivfflat + vector_cosine_ops.
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

        # Desactivamos escaneos secuenciales y ordenaciones normales
        # para obligar al planificador a mostrar si el índice vectorial
        # está realmente disponible para esta consulta.
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

        # El plan debe mencionar el índice creado en R42.
        assert "ix_document_embeddings_embedding_vector_cosine" in explain_plan
    finally:
        db.close()