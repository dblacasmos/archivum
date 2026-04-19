import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.documents.models import (
    Document,
    DocumentAccess,
    DocumentChunk,
    DocumentMetadata,
    DocumentVersion,
)


class DocumentRepository:
    """
    Repositorio de acceso a datos para documentos, ACL, metadata y versiones.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_document_with_initial_version(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> Document:
        """
        Guarda un documento nuevo y su versión 1 en una sola transacción.
        """
        self.db.add(document)
        self.db.flush()

        version.document_id = document.id
        self.db.add(version)

        self.db.commit()
        self.db.refresh(document)
        return document

    def create_document(self, document: Document) -> Document:
        """
        Guarda un documento nuevo en base de datos.
        """
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        """
        Busca un documento por su ID.
        """
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
        """
        Busca un permiso explícito para un documento y un usuario.
        """
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

    def get_metadata_by_document_and_key(
        self,
        document_id: uuid.UUID,
        meta_key: str,
    ) -> DocumentMetadata | None:
        """
        Busca una metadata concreta por documento y clave.
        """
        stmt = select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id,
            DocumentMetadata.meta_key == meta_key,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert_document_metadata(
        self,
        document_id: uuid.UUID,
        meta_key: str,
        meta_value: str,
    ) -> DocumentMetadata:
        """
        Crea una metadata nueva o actualiza su valor si la clave ya existe.
        """
        existing_metadata = self.get_metadata_by_document_and_key(
            document_id=document_id,
            meta_key=meta_key,
        )

        if existing_metadata is not None:
            existing_metadata.meta_value = meta_value
            self.db.add(existing_metadata)
            self.db.commit()
            self.db.refresh(existing_metadata)
            return existing_metadata

        metadata_entry = DocumentMetadata(
            document_id=document_id,
            meta_key=meta_key,
            meta_value=meta_value,
        )

        self.db.add(metadata_entry)
        self.db.commit()
        self.db.refresh(metadata_entry)
        return metadata_entry

    def list_document_metadata(self, document_id: uuid.UUID) -> list[DocumentMetadata]:
        """
        Devuelve toda la metadata de un documento ordenada por clave.
        """
        stmt = (
            select(DocumentMetadata)
            .where(DocumentMetadata.document_id == document_id)
            .order_by(DocumentMetadata.meta_key.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_document_versions(self, document_id: uuid.UUID) -> int:
        """
        Cuenta cuántas versiones tiene un documento.
        """
        stmt = select(func.count(DocumentVersion.id)).where(
            DocumentVersion.document_id == document_id
        )
        return int(self.db.execute(stmt).scalar_one() or 0)

    def get_next_version_number(self, document_id: uuid.UUID) -> int:
        """
        Calcula el siguiente número de versión para un documento.
        """
        stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
        current_max = self.db.execute(stmt).scalar_one()
        return 1 if current_max is None else current_max + 1

    def create_document_version(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> DocumentVersion:
        """
        Guarda una nueva versión y actualiza el estado actual del documento.
        """
        document.title = version.title
        document.content = version.content
        document.original_filename = version.original_filename
        document.stored_filename = version.stored_filename
        document.storage_path = version.storage_path
        document.mime_type = version.mime_type
        document.size_bytes = version.size_bytes

        self.db.add(document)
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        self.db.refresh(document)
        return version

    def list_document_versions(self, document_id: uuid.UUID) -> list[DocumentVersion]:
        """
        Devuelve el historial de versiones de un documento.
        """
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_document_version(
        self,
        document_id: uuid.UUID,
        version_number: int,
    ) -> DocumentVersion | None:
        """
        Devuelve una versión concreta de un documento.
        """
        stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
        return self.db.execute(stmt).scalar_one_or_none()
    
    def save_extracted_text_for_version(
        self,
        version: DocumentVersion,
        extracted_text: str,
    ) -> DocumentVersion:
        """
        Guarda el texto extraído de una versión y marca
        la extracción como completada.
        """
        version.extracted_text = extracted_text
        version.extraction_status = "completed"
        version.extraction_error = None
        version.extracted_at = datetime.now(timezone.utc)

        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def save_extraction_error_for_version(
        self,
        version: DocumentVersion,
        error_message: str,
    ) -> DocumentVersion:
        """
        Guarda el error de extracción para dejar trazabilidad
        cuando el procesamiento falla.
        """
        version.extracted_text = None
        version.extraction_status = "failed"
        version.extraction_error = error_message
        version.extracted_at = None

        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version
    
    def delete_chunks_for_version(self, document_version_id: uuid.UUID) -> None:
        """
        Borra los chunks antiguos de una versión para poder regenerarlos
        sin duplicados cuando se repite el proceso.
        """
        version = self.db.get(DocumentVersion, document_version_id)
        if version is None:
            return

        for chunk in list(version.chunks):
            self.db.delete(chunk)

        self.db.flush()

    def save_chunks_for_version(
        self,
        document: Document,
        version: DocumentVersion,
        chunks_data: list[dict],
    ) -> list[DocumentChunk]:
        """
        Sustituye los chunks existentes de una versión por los nuevos.
        """
        self.delete_chunks_for_version(version.id)

        chunks: list[DocumentChunk] = []

        for chunk_data in chunks_data:
            chunk = DocumentChunk(
                document_id=document.id,
                document_version_id=version.id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                char_count=chunk_data["char_count"],
                start_char=chunk_data["start_char"],
                end_char=chunk_data["end_char"],
            )
            self.db.add(chunk)
            chunks.append(chunk)

        self.db.commit()

        for chunk in chunks:
            self.db.refresh(chunk)

        return chunks

    def list_chunks_for_version(
        self,
        document_version_id: uuid.UUID,
    ) -> list[DocumentChunk]:
        """
        Devuelve todos los chunks de una versión ordenados por posición.
        """
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_version_id == document_version_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self.db.execute(stmt).scalars().all())