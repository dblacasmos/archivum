import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.documents.models import Document, DocumentAccess


class DocumentRepository:
    """
    Repositorio de acceso a datos para documentos y permisos explícitos.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_document(self, document: Document) -> Document:
        # Guarda un documento nuevo
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        # Busca un documento por su ID
        return self.db.get(Document, document_id)

    def list_visible_documents(self, user) -> list[Document]:
        """
        Devuelve solo los documentos que el usuario puede ver.
        Regla:
        - admin ve todo
        - el resto ve los suyos y los compartidos con él
        """
        user_role_names = {role.name for role in user.roles}

        if "admin" in user_role_names:
            stmt = select(Document).order_by(Document.created_at.desc())
            return list(self.db.execute(stmt).scalars().all())

        stmt = (
            select(Document)
            .distinct()
            .outerjoin(
                DocumentAccess,
                DocumentAccess.document_id == Document.id,
            )
            .where(
                or_(
                    Document.owner_id == user.id,
                    DocumentAccess.user_id == user.id,
                )
            )
            .order_by(Document.created_at.desc())
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_explicit_access(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DocumentAccess | None:
        # Busca un permiso explícito para un documento y un usuario
        stmt = select(DocumentAccess).where(
            DocumentAccess.document_id == document_id,
            DocumentAccess.user_id == user_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def grant_read_access(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
    ) -> DocumentAccess:
        """
        Concede acceso de lectura si todavía no existe.
        """
        existing_access = self.get_explicit_access(document_id, user_id)
        if existing_access is not None:
            return existing_access

        access = DocumentAccess(
            document_id=document_id,
            user_id=user_id,
            granted_by_user_id=granted_by_user_id,
        )

        self.db.add(access)
        self.db.commit()
        self.db.refresh(access)
        return access