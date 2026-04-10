from passlib.context import CryptContext
from sqlalchemy import text
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.users.models import User
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = TestClient(app)


def setup_r12_data():
    """
    Prepara datos de prueba para R12:
    - roles base
    - tres usuarios: admin, editor y viewer
    - asignación de roles
    """
    db = SessionLocal()

    try:
        # Limpiamos tablas en orden seguro
        db.execute(text("DELETE FROM document_accesses"))
        db.execute(text("DELETE FROM documents"))
        db.execute(text("DELETE FROM user_roles"))
        db.execute(text("DELETE FROM refresh_tokens"))
        db.execute(text("DELETE FROM users"))
        db.execute(text("DELETE FROM roles"))
        db.commit()

        # Insertamos roles base
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

        admin_user = user_repo.create(
            User(
                email="admin@test.com",
                password_hash=pwd_context.hash("admin123"),
                display_name="Admin",
            )
        )

        editor_user = user_repo.create(
            User(
                email="editor@test.com",
                password_hash=pwd_context.hash("editor123"),
                display_name="Editor",
            )
        )

        viewer_user = user_repo.create(
            User(
                email="viewer@test.com",
                password_hash=pwd_context.hash("viewer123"),
                display_name="Viewer",
            )
        )

        admin_role = user_repo.get_role_by_name("admin")
        editor_role = user_repo.get_role_by_name("editor")
        viewer_role = user_repo.get_role_by_name("viewer")

        user_repo.assign_role(admin_user, admin_role)
        user_repo.assign_role(editor_user, editor_role)
        user_repo.assign_role(viewer_user, viewer_role)

        return {
            "admin": admin_user,
            "editor": editor_user,
            "viewer": viewer_user,
        }
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

    assert response.status_code == 200
    return response.json()["access_token"]


def test_p12_1_rbac_authorized_and_unauthorized_access():
    """
    P12.1:
    - editor puede crear documento
    - viewer NO puede crear documento
    - admin puede listar usuarios
    - editor NO puede listar usuarios
    """
    setup_r12_data()

    editor_token = login_and_get_access_token("editor@test.com", "editor123")
    viewer_token = login_and_get_access_token("viewer@test.com", "viewer123")
    admin_token = login_and_get_access_token("admin@test.com", "admin123")

    # editor sí puede crear documento
    response_create_editor = client.post(
        "/documents",
        json={"title": "Documento del editor", "content": "Contenido privado"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response_create_editor.status_code == 201

    # viewer no puede crear documento
    response_create_viewer = client.post(
        "/documents",
        json={"title": "Intento viewer", "content": "No debería poder"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response_create_viewer.status_code == 403

    # admin sí puede listar usuarios
    response_admin_list_users = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response_admin_list_users.status_code == 200

    # editor no puede listar usuarios
    response_editor_list_users = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response_editor_list_users.status_code == 403


def test_p12_2_document_access_by_ownership_and_acl():
    """
    P12.2:
    - el owner puede leer su documento
    - otro usuario sin permiso no puede leerlo
    - tras compartirlo, sí puede leerlo
    """
    setup_r12_data()

    editor_token = login_and_get_access_token("editor@test.com", "editor123")
    viewer_token = login_and_get_access_token("viewer@test.com", "viewer123")

    # Creamos un documento del editor
    response_create = client.post(
        "/documents",
        json={"title": "Documento privado", "content": "Solo owner al principio"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response_create.status_code == 201

    document_id = response_create.json()["id"]

    # El owner puede leer su documento
    response_owner_read = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response_owner_read.status_code == 200
    assert response_owner_read.json()["title"] == "Documento privado"

    # El viewer todavía no tiene acceso
    response_viewer_read_denied = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response_viewer_read_denied.status_code == 403

    # Obtenemos el ID real del viewer usando endpoint /auth/users como admin no,
    # así que lo sacamos de /auth/me haciendo login con el propio viewer
    response_me_viewer = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response_me_viewer.status_code == 200
    viewer_user_id = response_me_viewer.json()["id"]

    # El owner comparte el documento con el viewer
    response_share = client.post(
        f"/documents/{document_id}/share",
        json={"user_id": viewer_user_id},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response_share.status_code == 200

    # Ahora el viewer sí puede leerlo
    response_viewer_read_ok = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response_viewer_read_ok.status_code == 200
    assert response_viewer_read_ok.json()["title"] == "Documento privado"

    # Y además debe aparecer en su listado visible
    response_viewer_list = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response_viewer_list.status_code == 200
    assert len(response_viewer_list.json()) == 1
    assert response_viewer_list.json()[0]["id"] == document_id