from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = TestClient(app)


def setup_r21_data() -> None:
    """
    Prepara los datos mínimos para probar R21.

    Se crean:
    - roles base
    - un usuario editor que será owner del documento
    - un usuario viewer para comprobar accesos
    """
    db = SessionLocal()

    try:
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

        user_repo = UserRepository(db)

        editor_user = user_repo.create(
            User(
                email="r21_editor@test.com",
                password_hash=pwd_context.hash("r21password"),
                display_name="Editor R21",
            )
        )

        viewer_user = user_repo.create(
            User(
                email="r21_viewer@test.com",
                password_hash=pwd_context.hash("r21password"),
                display_name="Viewer R21",
            )
        )

        editor_role = user_repo.get_role_by_name("editor")
        viewer_role = user_repo.get_role_by_name("viewer")

        user_repo.assign_role(editor_user, editor_role)
        user_repo.assign_role(viewer_user, viewer_role)

    finally:
        db.close()


def login_and_get_access_token(email: str, password: str) -> str:
    """
    Hace login y devuelve el access token del usuario indicado.
    """
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_document_for_r21(access_token: str) -> str:
    """
    Crea un documento base para poder asociarle metadata.
    """
    response = client.post(
        "/documents/upload",
        data={"title": "Documento con metadata"},
        files={
            "file": (
                "metadata.txt",
                b"Contenido del documento de prueba para metadata",
                "text/plain",
            )
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_p21_1_document_metadata_management():
    """
    P21.1:
    Verifica que se puede crear, actualizar y consultar metadata
    asociada a un documento.
    """
    setup_r21_data()

    editor_token = login_and_get_access_token("r21_editor@test.com", "r21password")
    document_id = create_document_for_r21(editor_token)

    create_response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": "category", "value": "manual"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert create_response.status_code == 201, create_response.text
    create_body = create_response.json()

    assert create_body["document_id"] == document_id
    assert create_body["meta_key"] == "category"
    assert create_body["meta_value"] == "manual"

    update_response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": "category", "value": "guia"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert update_response.status_code == 201, update_response.text
    update_body = update_response.json()

    assert update_body["document_id"] == document_id
    assert update_body["meta_key"] == "category"
    assert update_body["meta_value"] == "guia"

    second_metadata_response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": "language", "value": "es"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert second_metadata_response.status_code == 201, second_metadata_response.text

    list_response = client.get(
        f"/documents/{document_id}/metadata",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert list_response.status_code == 200, list_response.text
    list_body = list_response.json()

    assert list_body["document_id"] == document_id
    assert {"key": "category", "value": "guia"} in list_body["items"]
    assert {"key": "language", "value": "es"} in list_body["items"]

    single_response = client.get(
        f"/documents/{document_id}/metadata/category",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert single_response.status_code == 200, single_response.text
    single_body = single_response.json()

    assert single_body["meta_key"] == "category"
    assert single_body["meta_value"] == "guia"

    db = SessionLocal()
    try:
        rows = db.execute(
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

        assert len(rows) == 2
        assert rows[0]["meta_key"] == "category"
        assert rows[0]["meta_value"] == "guia"
        assert rows[1]["meta_key"] == "language"
        assert rows[1]["meta_value"] == "es"
    finally:
        db.close()


def test_p21_2_viewer_cannot_manage_metadata_of_foreign_document():
    """
    Caso adicional:
    un viewer que no es owner no puede modificar la metadata.
    """
    setup_r21_data()

    editor_token = login_and_get_access_token("r21_editor@test.com", "r21password")
    viewer_token = login_and_get_access_token("r21_viewer@test.com", "r21password")
    document_id = create_document_for_r21(editor_token)

    response = client.post(
        f"/documents/{document_id}/metadata",
        json={"key": "category", "value": "privado"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403, response.text