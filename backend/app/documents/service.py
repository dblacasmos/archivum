import uuid

from app.documents.models import Document
from app.documents.repository import DocumentRepository
from app.users.repository import UserRepository


class DocumentService:
    """
    Servicio con la lógica de permisos sobre documentos.
    Aquí vive la parte importante de R12.
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        user_repo: UserRepository,
    ):
        self.document_repo = document_repo
        self.user_repo = user_repo

    def _get_role_names(self, user) -> set[str]:
        # Devuelve los roles del usuario como conjunto
        return {role.name for role in user.roles}

    def _is_admin(self, user) -> bool:
        # Comprueba si el usuario tiene rol admin
        return "admin" in self._get_role_names(user)

    def _can_create_document(self, user) -> bool:
        """
        Solo admin y editor pueden crear documentos.
        """
        allowed_roles = {"admin", "editor"}
        return bool(self._get_role_names(user).intersection(allowed_roles))

    def _can_read_document(self, user, document: Document) -> bool:
        """
        Reglas de lectura:
        - admin puede leer todo
        - owner puede leer su documento
        - usuario con permiso explícito puede leerlo
        """
        if self._is_admin(user):
            return True

        if document.owner_id == user.id:
            return True

        access = self.document_repo.get_explicit_access(document.id, user.id)
        return access is not None

    def _can_share_document(self, user, document: Document) -> bool:
        """
        Reglas para compartir:
        - admin puede compartir cualquier documento
        - owner puede compartir su documento
        """
        if self._is_admin(user):
            return True

        return document.owner_id == user.id

    def create_document(self, current_user, title: str, content: str | None) -> Document:
        """
        Crea un documento si el usuario tiene rol suficiente.
        """
        if not self._can_create_document(current_user):
            raise PermissionError("No tienes permisos para crear documentos")

        document = Document(
            title=title,
            content=content,
            owner_id=current_user.id,
        )

        return self.document_repo.create_document(document)

    def list_visible_documents(self, current_user) -> list[Document]:
        """
        Devuelve los documentos visibles para el usuario autenticado.
        """
        return self.document_repo.list_visible_documents(current_user)

    def get_document_for_read(self, current_user, document_id: uuid.UUID) -> Document:
        """
        Devuelve un documento solo si el usuario puede leerlo.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para leer este documento")

        return document

    def share_document(
        self,
        current_user,
        document_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ):
        """
        Comparte un documento con otro usuario si el actor tiene permiso.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        target_user = self.user_repo.find_by_id(target_user_id)
        if target_user is None:
            raise ValueError("Usuario destino no encontrado")

        if not self._can_share_document(current_user, document):
            raise PermissionError("No tienes permisos para compartir este documento")

        return self.document_repo.grant_read_access(
            document_id=document.id,
            user_id=target_user.id,
            granted_by_user_id=current_user.id,
        )