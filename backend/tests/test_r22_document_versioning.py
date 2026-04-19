from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = TestClient(app)


def setup_r22_data() -> None:
    """
    Prepara los datos mínimos para probar R22.
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
                email="r22_editor@test.com",
                password_hash=pwd_context.hash("r22password"),
                display_name="Editor R22",
            )
        )

        viewer_user = user_repo.create(
            User(
                email="r22_viewer@test.com",
                password_hash=pwd_context.hash("r22password"),
                display_name="Viewer R22",
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
    Hace login y devuelve el access token.
    """
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_base_document(access_token: str) -> str:
    """
    Crea un documento base sobre el que luego se crearán versiones.
    """
    response = client.post(
        "/documents/upload",
        data={"title": "Manual inicial"},
        files={
            "file": (
                "manual_v1.txt",
                b"Contenido inicial del documento",
                "text/plain",
            )
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_p22_1_document_versioning():
    """
    P22.1:
    Verifica que se puede crear una nueva versión
    y consultar el historial completo.
    """
    setup_r22_data()

    editor_token = login_and_get_access_token("r22_editor@test.com", "r22password")
    document_id = create_base_document(editor_token)

    create_version_response = client.post(
        f"/documents/{document_id}/versions",
        data={"title": "Manual actualizado"},
        files={
            "file": (
                "manual_v2.txt",
                b"Contenido actualizado del documento",
                "text/plain",
            )
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert create_version_response.status_code == 201, create_version_response.text
    create_version_body = create_version_response.json()

    assert create_version_body["document_id"] == document_id
    assert create_version_body["version_number"] == 2
    assert create_version_body["title"] == "Manual actualizado"
    assert create_version_body["original_filename"] == "manual_v2.txt"

    list_response = client.get(
        f"/documents/{document_id}/versions",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert list_response.status_code == 200, list_response.text
    list_body = list_response.json()

    assert list_body["document_id"] == document_id
    assert len(list_body["items"]) == 2
    assert list_body["items"][0]["version_number"] == 1
    assert list_body["items"][1]["version_number"] == 2

    version_detail_response = client.get(
        f"/documents/{document_id}/versions/2",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert version_detail_response.status_code == 200, version_detail_response.text
    version_detail_body = version_detail_response.json()

    assert version_detail_body["version_number"] == 2
    assert version_detail_body["title"] == "Manual actualizado"
    assert version_detail_body["original_filename"] == "manual_v2.txt"

    document_response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert document_response.status_code == 200, document_response.text
    document_body = document_response.json()

    assert document_body["title"] == "Manual actualizado"
    assert document_body["original_filename"] == "manual_v2.txt"

    db = SessionLocal()
    try:
        versions = db.execute(
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

        assert len(versions) == 2
        assert versions[0]["version_number"] == 1
        assert versions[0]["title"] == "Manual inicial"
        assert versions[0]["original_filename"] == "manual_v1.txt"
        assert versions[1]["version_number"] == 2
        assert versions[1]["title"] == "Manual actualizado"
        assert versions[1]["original_filename"] == "manual_v2.txt"
    finally:
        db.close()


def test_p22_2_viewer_cannot_create_new_version_of_foreign_document():
    """
    Caso adicional:
    un viewer que no es owner no puede crear nuevas versiones.
    """
    setup_r22_data()

    editor_token = login_and_get_access_token("r22_editor@test.com", "r22password")
    viewer_token = login_and_get_access_token("r22_viewer@test.com", "r22password")
    document_id = create_base_document(editor_token)

    response = client.post(
        f"/documents/{document_id}/versions",
        data={"title": "Intento no autorizado"},
        files={
            "file": (
                "manual_fake.txt",
                b"Esto no deberia dejarse crear",
                "text/plain",
            )
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403, response.text