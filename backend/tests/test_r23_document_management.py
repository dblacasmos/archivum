import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

# Cliente de pruebas para lanzar peticiones HTTP contra la API.
client = TestClient(app)

# Contexto para cifrar contraseñas de usuarios de prueba.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def clean_document_storage() -> None:
    """
    Limpia la carpeta de almacenamiento de documentos antes de cada test.
    Así evitamos que un test reutilice archivos de otro test anterior.
    """
    upload_dir = Path(settings.upload_dir)

    if upload_dir.exists():
        shutil.rmtree(upload_dir)


def reset_database_for_r23() -> None:
    """
    Reinicia los datos necesarios para R23.

    Este test no busca validar la seguridad ni el alta de usuarios.
    Solo deja preparado un escenario limpio y controlado para probar
    la gestión documental de forma integrada.
    """
    db = SessionLocal()

    try:
        # Borramos primero tablas hijas y luego tablas padre
        # para no romper claves foráneas.
        db.execute(text("DELETE FROM document_versions"))
        db.execute(text("DELETE FROM document_metadata"))
        db.execute(text("DELETE FROM document_accesses"))
        db.execute(text("DELETE FROM documents"))
        db.execute(text("DELETE FROM user_roles"))
        db.execute(text("DELETE FROM refresh_tokens"))
        db.execute(text("DELETE FROM users"))
        db.execute(text("DELETE FROM roles"))
        db.commit()

        # Insertamos los roles mínimos del sistema.
        db.execute(
            text(
                """
                INSERT INTO roles (id, name, description) VALUES
                (gen_random_uuid(), 'admin', 'Administrador del sistema'),
                (gen_random_uuid(), 'editor', 'Editor documental'),
                (gen_random_uuid(), 'viewer', 'Lector de documentos');
                """
            )
        )
        db.commit()

        user_repo = UserRepository(db)

        # Creamos un usuario editor que será el propietario del documento.
        editor_user = user_repo.create(
            User(
                email="r23_editor@test.com",
                password_hash=pwd_context.hash("123456"),
                display_name="Editor R23",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        user_repo.assign_role(editor_user, editor_role)

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

    body = response.json()
    assert "access_token" in body

    return body["access_token"]


def upload_document(token: str, title: str, filename: str, content: bytes) -> dict:
    """
    Sube un documento al sistema.
    """
    response = client.post(
        "/documents/upload",
        data={"title": title},
        files={"file": (filename, content, "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_or_update_metadata(token: str, document_id: str, key: str, value: str) -> dict:
    """
    Crea o actualiza una entrada de metadata asociada a un documento.
    """
    response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": key, "value": value},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_new_document_version(
    token: str,
    document_id: str,
    title: str,
    filename: str,
    content: bytes,
) -> dict:
    """
    Crea una nueva versión de un documento ya existente.
    """
    response = client.post(
        f"/documents/{document_id}/versions",
        data={"title": title},
        files={"file": (filename, content, "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()


def get_document(token: str, document_id: str) -> dict:
    """
    Recupera el estado actual del documento.
    """
    response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def get_document_metadata(token: str, document_id: str) -> dict:
    """
    Recupera toda la metadata asociada al documento.
    """
    response = client.get(
        f"/documents/{document_id}/metadata",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def get_document_versions(token: str, document_id: str) -> dict:
    """
    Recupera el historial de versiones del documento.
    """
    response = client.get(
        f"/documents/{document_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    return response.json()


def test_p23_1_integrated_upload_plus_metadata():
    """
    P23.1 - Prueba integrada de subida + metadata

    Objetivo real:
    comprobar que, tras subir un documento, se puede enriquecer
    inmediatamente con metadata y recuperar ambos elementos de forma coherente.
    """
    clean_document_storage()
    reset_database_for_r23()

    token = login_and_get_token("r23_editor@test.com", "123456")

    # Paso 1: subimos el documento.
    document = upload_document(
        token=token,
        title="Manual de calidad",
        filename="manual_calidad_v1.txt",
        content=b"Contenido inicial del manual de calidad",
    )

    document_id = document["id"]

    # Paso 2: asociamos metadata al documento recién creado.
    create_or_update_metadata(token, document_id, "category", "calidad")
    create_or_update_metadata(token, document_id, "language", "es")
    create_or_update_metadata(token, document_id, "department", "operaciones")

    # Paso 3: recuperamos el documento y su metadata para comprobar
    # que ambas partes encajan entre sí.
    current_document = get_document(token, document_id)
    metadata = get_document_metadata(token, document_id)

    # Validamos el estado actual del documento.
    assert current_document["id"] == document_id
    assert current_document["title"] == "Manual de calidad"
    assert current_document["original_filename"] == "manual_calidad_v1.txt"
    assert current_document["mime_type"] == "text/plain"
    assert current_document["size_bytes"] > 0
    assert current_document["owner_id"] is not None

    # Validamos que la metadata recuperada pertenece al mismo documento.
    assert metadata["document_id"] == document_id
    assert {"key": "category", "value": "calidad"} in metadata["items"]
    assert {"key": "language", "value": "es"} in metadata["items"]
    assert {"key": "department", "value": "operaciones"} in metadata["items"]


def test_p23_2_versioning_on_existing_document_with_metadata():
    """
    P23.2 - Prueba de versionado sobre documento existente

    Objetivo real:
    comprobar que el versionado funciona sobre un documento ya creado
    y ya enriquecido con metadata, no sobre un recurso aislado.
    """
    clean_document_storage()
    reset_database_for_r23()

    token = login_and_get_token("r23_editor@test.com", "123456")

    # Creamos el documento base.
    document = upload_document(
        token=token,
        title="Procedimiento interno",
        filename="procedimiento_v1.txt",
        content=b"Version inicial del procedimiento",
    )

    document_id = document["id"]

    # Añadimos metadata antes de versionar.
    create_or_update_metadata(token, document_id, "category", "procedimiento")
    create_or_update_metadata(token, document_id, "status", "borrador")

    # Creamos una nueva versión del mismo documento.
    new_version = create_new_document_version(
        token=token,
        document_id=document_id,
        title="Procedimiento interno revisado",
        filename="procedimiento_v2.txt",
        content=b"Version revisada del procedimiento",
    )

    versions = get_document_versions(token, document_id)
    current_document = get_document(token, document_id)
    metadata = get_document_metadata(token, document_id)

    # La nueva versión debe existir y ser la número 2.
    assert new_version["document_id"] == document_id
    assert new_version["version_number"] == 2
    assert new_version["title"] == "Procedimiento interno revisado"
    assert new_version["original_filename"] == "procedimiento_v2.txt"

    # El documento actual debe reflejar el último estado.
    assert current_document["id"] == document_id
    assert current_document["title"] == "Procedimiento interno revisado"
    assert current_document["original_filename"] == "procedimiento_v2.txt"

    # El historial debe conservar ambas versiones.
    assert versions["document_id"] == document_id
    assert len(versions["items"]) == 2

    assert versions["items"][0]["version_number"] == 1
    assert versions["items"][0]["title"] == "Procedimiento interno"
    assert versions["items"][0]["original_filename"] == "procedimiento_v1.txt"

    assert versions["items"][1]["version_number"] == 2
    assert versions["items"][1]["title"] == "Procedimiento interno revisado"
    assert versions["items"][1]["original_filename"] == "procedimiento_v2.txt"

    # La metadata debe seguir asociada al documento lógico tras versionar.
    assert {"key": "category", "value": "procedimiento"} in metadata["items"]
    assert {"key": "status", "value": "borrador"} in metadata["items"]


def test_p23_3_document_metadata_versions_consistency():
    """
    P23.3 - Prueba de coherencia entre documento, metadata y versiones

    Objetivo real:
    validar el bloque completo como conjunto.

    No comprobamos solo que cada endpoint responda bien.
    Comprobamos que el sistema mantiene una relación coherente entre:
    - el documento actual
    - su metadata
    - su historial de versiones
    - la persistencia en base de datos
    """
    clean_document_storage()
    reset_database_for_r23()

    token = login_and_get_token("r23_editor@test.com", "123456")

    # 1. Creamos el documento inicial.
    document = upload_document(
        token=token,
        title="Politica interna",
        filename="politica_v1.txt",
        content=b"Contenido de la politica version 1",
    )

    document_id = document["id"]

    # 2. Añadimos metadata.
    create_or_update_metadata(token, document_id, "category", "normativa")
    create_or_update_metadata(token, document_id, "language", "es")
    create_or_update_metadata(token, document_id, "scope", "interno")

    # 3. Creamos nueva versión.
    create_new_document_version(
        token=token,
        document_id=document_id,
        title="Politica interna actualizada",
        filename="politica_v2.txt",
        content=b"Contenido de la politica version 2",
    )

    # 4. Consultamos la vista actual del documento, la metadata y el historial.
    current_document = get_document(token, document_id)
    metadata = get_document_metadata(token, document_id)
    versions = get_document_versions(token, document_id)

    # 5. Validamos coherencia funcional desde la API.

    # El documento actual debe reflejar la última versión.
    assert current_document["title"] == "Politica interna actualizada"
    assert current_document["original_filename"] == "politica_v2.txt"
    assert current_document["mime_type"] == "text/plain"
    assert current_document["size_bytes"] > 0

    # La metadata debe seguir asociada al documento principal.
    assert metadata["document_id"] == document_id
    assert {"key": "category", "value": "normativa"} in metadata["items"]
    assert {"key": "language", "value": "es"} in metadata["items"]
    assert {"key": "scope", "value": "interno"} in metadata["items"]

    # El historial debe conservar ambas versiones en orden.
    assert versions["document_id"] == document_id
    assert len(versions["items"]) == 2

    assert versions["items"][0]["version_number"] == 1
    assert versions["items"][0]["title"] == "Politica interna"
    assert versions["items"][0]["original_filename"] == "politica_v1.txt"

    assert versions["items"][1]["version_number"] == 2
    assert versions["items"][1]["title"] == "Politica interna actualizada"
    assert versions["items"][1]["original_filename"] == "politica_v2.txt"

    # 6. Validamos coherencia real en base de datos.
    db = SessionLocal()

    try:
        document_row = db.execute(
            text(
                """
                SELECT id, title, original_filename, mime_type, size_bytes
                FROM documents
                WHERE id = :document_id
                """
            ),
            {"document_id": document_id},
        ).mappings().first()

        metadata_rows = db.execute(
            text(
                """
                SELECT meta_key, meta_value
                FROM document_metadata
                WHERE document_id = :document_id
                ORDER BY meta_key ASC
                """
            ),
            {"document_id": document_id},
        ).mappings().all()

        version_rows = db.execute(
            text(
                """
                SELECT version_number, title, original_filename
                FROM document_versions
                WHERE document_id = :document_id
                ORDER BY version_number ASC
                """
            ),
            {"document_id": document_id},
        ).mappings().all()

        # El registro principal del documento debe reflejar la última versión.
        assert document_row is not None
        assert str(document_row["id"]) == document_id
        assert document_row["title"] == "Politica interna actualizada"
        assert document_row["original_filename"] == "politica_v2.txt"
        assert document_row["mime_type"] == "text/plain"
        assert document_row["size_bytes"] > 0

        # La metadata debe seguir viva y correctamente vinculada al documento.
        assert {"meta_key": "category", "meta_value": "normativa"} in metadata_rows
        assert {"meta_key": "language", "meta_value": "es"} in metadata_rows
        assert {"meta_key": "scope", "meta_value": "interno"} in metadata_rows

        # El historial debe contener las dos versiones.
        assert len(version_rows) == 2

        assert version_rows[0]["version_number"] == 1
        assert version_rows[0]["title"] == "Politica interna"
        assert version_rows[0]["original_filename"] == "politica_v1.txt"

        assert version_rows[1]["version_number"] == 2
        assert version_rows[1]["title"] == "Politica interna actualizada"
        assert version_rows[1]["original_filename"] == "politica_v2.txt"

    finally:
        db.close()