import os
import uuid

from fastapi import UploadFile

from app.documents.models import Document, DocumentChunk, DocumentMetadata, DocumentVersion
from app.documents.repository import DocumentRepository
from app.documents.storage import DocumentStorageService
from app.users.repository import UserRepository
from app.documents.extraction import TextExtractionService
from app.documents.chunking import TextChunkingService

class DocumentService:
    """
    Servicio con la lógica de negocio de documentos.

    Aquí conviven varios casos:
    - creación manual simple
    - subida real de archivos
    - gestión de metadata básica
    - versionado de documentos
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        user_repo: UserRepository,
        storage_service: DocumentStorageService,
        extraction_service: TextExtractionService,
        chunking_service: TextChunkingService,
    ):
        self.document_repo = document_repo
        self.user_repo = user_repo
        self.storage_service = storage_service
        self.extraction_service = extraction_service
        self.chunking_service = chunking_service

    def _get_role_names(self, user) -> set[str]:
        """
        Devuelve los roles del usuario como conjunto.
        """
        return {role.name for role in user.roles}

    def _is_admin(self, user) -> bool:
        """
        Comprueba si el usuario tiene rol admin.
        """
        return "admin" in self._get_role_names(user)

    def _can_create_document(self, user) -> bool:
        """
        Solo admin y editor pueden crear o subir documentos.
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

    def _can_manage_metadata(self, user, document: Document) -> bool:
        """
        Reglas para crear o actualizar metadata:
        - admin puede gestionar cualquier metadata
        - owner puede gestionar la metadata de su documento
        """
        if self._is_admin(user):
            return True

        return document.owner_id == user.id

    def _can_manage_versions(self, user, document: Document) -> bool:
        """
        Reglas para crear nuevas versiones:
        - admin puede versionar cualquier documento
        - owner puede versionar su documento
        """
        if self._is_admin(user):
            return True

        return document.owner_id == user.id

    def _build_initial_version_from_document(
        self,
        document: Document,
        created_by_user_id,
    ) -> DocumentVersion:
        """
        Construye la versión 1 usando el estado actual del documento.
        """
        return DocumentVersion(
            document_id=document.id,
            version_number=1,
            title=document.title,
            content=document.content,
            original_filename=document.original_filename,
            stored_filename=document.stored_filename,
            storage_path=document.storage_path,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            created_by_user_id=created_by_user_id,
        )

    def _ensure_initial_version_exists(self, document: Document) -> None:
        """
        Si existen documentos antiguos creados antes de R22,
        genera su versión 1 a partir del estado actual.
        """
        current_count = self.document_repo.count_document_versions(document.id)
        if current_count > 0:
            return

        initial_version = self._build_initial_version_from_document(
            document=document,
            created_by_user_id=document.owner_id,
        )

        self.document_repo.create_document_version(
            document=document,
            version=initial_version,
        )

    def create_document(self, current_user, title: str, content: str | None) -> Document:
        """
        Crea un documento lógico simple y también su versión 1.
        """
        if not self._can_create_document(current_user):
            raise PermissionError("No tienes permisos para crear documentos")

        document = Document(
            title=title,
            content=content,
            owner_id=current_user.id,
        )

        version = DocumentVersion(
            version_number=1,
            title=title,
            content=content,
            original_filename=None,
            stored_filename=None,
            storage_path=None,
            mime_type=None,
            size_bytes=None,
            created_by_user_id=current_user.id,
        )

        return self.document_repo.create_document_with_initial_version(
            document=document,
            version=version,
        )

    async def upload_document(
        self,
        current_user,
        upload_file: UploadFile,
        title: str | None = None,
    ) -> Document:
        """
        Guarda un archivo en disco, registra su referencia
        y crea también la versión 1.
        """
        if not self._can_create_document(current_user):
            raise PermissionError("No tienes permisos para subir documentos")

        stored_file = await self.storage_service.save_upload(
            upload_file=upload_file,
            owner_id=str(current_user.id),
        )

        final_title = title.strip() if title and title.strip() else os.path.splitext(
            stored_file.original_filename
        )[0]

        document = Document(
            title=final_title,
            content=None,
            original_filename=stored_file.original_filename,
            stored_filename=stored_file.stored_filename,
            storage_path=stored_file.storage_path,
            mime_type=stored_file.mime_type,
            size_bytes=stored_file.size_bytes,
            owner_id=current_user.id,
        )

        version = DocumentVersion(
            version_number=1,
            title=final_title,
            content=None,
            original_filename=stored_file.original_filename,
            stored_filename=stored_file.stored_filename,
            storage_path=stored_file.storage_path,
            mime_type=stored_file.mime_type,
            size_bytes=stored_file.size_bytes,
            created_by_user_id=current_user.id,
        )

        return self.document_repo.create_document_with_initial_version(
            document=document,
            version=version,
        )

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

    def upsert_document_metadata(
        self,
        current_user,
        document_id: uuid.UUID,
        meta_key: str,
        meta_value: str,
    ) -> DocumentMetadata:
        """
        Crea o actualiza una metadata de un documento.
        """
        clean_key = meta_key.strip().lower()
        clean_value = meta_value.strip()

        if not clean_key:
            raise ValueError("La clave de metadata no puede estar vacía")

        if not clean_value:
            raise ValueError("El valor de metadata no puede estar vacío")

        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_manage_metadata(current_user, document):
            raise PermissionError("No tienes permisos para gestionar la metadata de este documento")

        return self.document_repo.upsert_document_metadata(
            document_id=document.id,
            meta_key=clean_key,
            meta_value=clean_value,
        )

    def list_document_metadata(
        self,
        current_user,
        document_id: uuid.UUID,
    ) -> list[DocumentMetadata]:
        """
        Devuelve la metadata de un documento si el usuario puede leerlo.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para consultar la metadata de este documento")

        return self.document_repo.list_document_metadata(document_id=document.id)

    def get_document_metadata_by_key(
        self,
        current_user,
        document_id: uuid.UUID,
        meta_key: str,
    ) -> DocumentMetadata:
        """
        Devuelve una metadata concreta por clave si el usuario puede leer el documento.
        """
        clean_key = meta_key.strip().lower()

        if not clean_key:
            raise ValueError("La clave de metadata no puede estar vacía")

        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para consultar la metadata de este documento")

        metadata_entry = self.document_repo.get_metadata_by_document_and_key(
            document_id=document.id,
            meta_key=clean_key,
        )

        if metadata_entry is None:
            raise ValueError("Metadata no encontrada para la clave indicada")

        return metadata_entry

    async def create_document_version(
        self,
        current_user,
        document_id: uuid.UUID,
        title: str | None = None,
        content: str | None = None,
        upload_file: UploadFile | None = None,
    ) -> DocumentVersion:
        """
        Crea una nueva versión de un documento ya existente.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_manage_versions(current_user, document):
            raise PermissionError("No tienes permisos para crear versiones de este documento")

        self._ensure_initial_version_exists(document)

        next_version_number = self.document_repo.get_next_version_number(document.id)

        if upload_file is not None and upload_file.filename:
            stored_file = await self.storage_service.save_upload(
                upload_file=upload_file,
                owner_id=str(document.owner_id),
            )

            final_title = title.strip() if title and title.strip() else os.path.splitext(
                stored_file.original_filename
            )[0]

            version = DocumentVersion(
                document_id=document.id,
                version_number=next_version_number,
                title=final_title,
                content=None,
                original_filename=stored_file.original_filename,
                stored_filename=stored_file.stored_filename,
                storage_path=stored_file.storage_path,
                mime_type=stored_file.mime_type,
                size_bytes=stored_file.size_bytes,
                created_by_user_id=current_user.id,
            )

            return self.document_repo.create_document_version(
                document=document,
                version=version,
            )

        if content is not None:
            final_title = title.strip() if title and title.strip() else document.title
            clean_content = content.strip()

            if not clean_content:
                raise ValueError("El contenido de la nueva versión no puede estar vacío")

            version = DocumentVersion(
                document_id=document.id,
                version_number=next_version_number,
                title=final_title,
                content=clean_content,
                original_filename=None,
                stored_filename=None,
                storage_path=None,
                mime_type=None,
                size_bytes=None,
                created_by_user_id=current_user.id,
            )

            return self.document_repo.create_document_version(
                document=document,
                version=version,
            )

        raise ValueError("Debes enviar un archivo o contenido para crear una nueva versión")

    def list_document_versions(
        self,
        current_user,
        document_id: uuid.UUID,
    ) -> list[DocumentVersion]:
        """
        Devuelve el historial de versiones si el usuario puede leer el documento.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para consultar las versiones de este documento")

        self._ensure_initial_version_exists(document)
        return self.document_repo.list_document_versions(document.id)

    def get_document_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
    ) -> DocumentVersion:
        """
        Devuelve una versión concreta si el usuario puede leer el documento.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para consultar las versiones de este documento")

        self._ensure_initial_version_exists(document)

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        return version
    
    def extract_text_from_document_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
    ) -> DocumentVersion:
        """
        Ejecuta la extracción de texto sobre una versión concreta
        y persiste el resultado en base de datos.

        Como esta operación modifica el estado persistido,
        solo la pueden lanzar admin o owner.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_manage_versions(current_user, document):
            raise PermissionError("No tienes permisos para extraer texto de este documento")

        self._ensure_initial_version_exists(document)

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        try:
            extraction_result = self.extraction_service.extract_from_version(version)

            return self.document_repo.save_extracted_text_for_version(
                version=version,
                extracted_text=extraction_result.extracted_text,
            )
        except ValueError as exc:
            self.document_repo.save_extraction_error_for_version(
                version=version,
                error_message=str(exc),
            )
            raise

    def get_extracted_text_for_document_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
    ) -> DocumentVersion:
        """
        Devuelve el texto extraído ya persistido de una versión concreta.

        Esta operación es solo de lectura, por lo que basta con
        que el usuario tenga permiso de lectura sobre el documento.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para consultar el texto extraído")

        self._ensure_initial_version_exists(document)

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        if version.extracted_text is None or not version.extracted_text.strip():
            raise ValueError("Esta versión todavía no tiene texto extraído")

        return version
    
    def chunk_document_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[DocumentChunk]:
        """
        Genera y persiste los chunks de una versión concreta.

        Solo owner o admin pueden lanzar este proceso porque
        modifica información persistida del sistema.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_manage_versions(current_user, document):
            raise PermissionError("No tienes permisos para fragmentar este documento")

        self._ensure_initial_version_exists(document)

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        if version.extracted_text is None or not version.extracted_text.strip():
            raise ValueError("La versión indicada no tiene texto extraído para fragmentar")

        chunk_pieces = self.chunking_service.chunk_text(
            text=version.extracted_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunks_data = [
            {
                "chunk_index": item.chunk_index,
                "content": item.content,
                "char_count": item.char_count,
                "start_char": item.start_char,
                "end_char": item.end_char,
            }
            for item in chunk_pieces
        ]

        return self.document_repo.save_chunks_for_version(
            document=document,
            version=version,
            chunks_data=chunks_data,
        )

    def get_chunks_for_document_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
    ) -> list[DocumentChunk]:
        """
        Devuelve los chunks persistidos de una versión concreta.
        """
        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_document(current_user, document):
            raise PermissionError("No tienes permisos para consultar los chunks")

        self._ensure_initial_version_exists(document)

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        chunks = self.document_repo.list_chunks_for_version(version.id)

        if not chunks:
            raise ValueError("Esta versión todavía no tiene chunks generados")

        return chunks