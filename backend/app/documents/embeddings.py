import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.models import Document, DocumentEmbedding
from app.documents.repository import DocumentRepository


@dataclass
class EmbeddingProviderResult:
    """
    Resultado simple devuelto por el proveedor de embeddings.
    """

    model_name: str
    vectors: list[list[float]]


class OpenAIEmbeddingClient:
    """
    Cliente de embeddings.

    En producción este cliente llamaría al endpoint real
    de OpenAI.

    Para las pruebas locales del TFG se utilizan embeddings
    mock para evitar dependencias externas y costes asociados
    al uso de APIs reales.
    """

    def generate_embeddings(
        self,
        texts: list[str],
        model_name: str | None = None,
    ) -> EmbeddingProviderResult:
        """
        Genera embeddings falsos para pruebas locales.

        Esta implementación permite validar:
        - chunking
        - pgvector
        - retrieval semántico
        - búsqueda híbrida
        - flujo RAG
        - frontend

        sin depender de OpenAI.
        """

        if not texts:
            raise ValueError(
                "No hay chunks disponibles para generar embeddings"
            )

        clean_texts: list[str] = []

        for text in texts:
            clean_text = text.strip()

            if not clean_text:
                raise ValueError(
                    "No se puede generar un embedding desde un chunk vacío"
                )

            clean_texts.append(clean_text)

        """
        Nombre ficticio del modelo utilizado
        durante las pruebas.
        """
        final_model_name = (
            model_name or "mock-embedding-model"
        )

        all_vectors: list[list[float]] = []

        for index, text in enumerate(clean_texts):
            """
            Generamos un vector fake de 1536 dimensiones.

            Se añade una pequeña variación por chunk
            para evitar que todos los embeddings sean
            exactamente iguales.
            """

            base_value = 0.001 + (index * 0.0001)

            fake_vector = [base_value] * 1536

            all_vectors.append(fake_vector)

        return EmbeddingProviderResult(
            model_name=final_model_name,
            vectors=all_vectors,
        )

    def _extract_error_message(
        self,
        response: httpx.Response,
    ) -> str:
        """
        Método conservado únicamente para mantener
        compatibilidad estructural con la versión
        real del cliente.
        """

        try:
            payload = response.json()

        except Exception:
            return response.text or "Error desconocido"

        error_data = payload.get("error")

        if isinstance(error_data, dict):
            return (
                error_data.get("message")
                or "Error desconocido"
            )

        return (
            payload.get("message")
            or response.text
            or "Error desconocido"
        )


class DocumentEmbeddingService:
    """
    Lógica de negocio para R40.

    Esta capa:
    - valida permisos
    - recupera el documento y su versión
    - recoge los chunks persistidos
    - llama al modelo de embeddings
    - persiste el resultado asociado a cada chunk
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        embedding_repo: DocumentEmbeddingRepository,
        embedding_client: OpenAIEmbeddingClient,
    ):
        self.document_repo = document_repo
        self.embedding_repo = embedding_repo
        self.embedding_client = embedding_client

    def _get_role_names(self, user) -> set[str]:
        """
        Devuelve los roles del usuario como conjunto.
        """
        return {role.name for role in user.roles}

    def _is_admin(self, user) -> bool:
        """
        Comprueba si el usuario es admin.
        """
        return "admin" in self._get_role_names(user)

    def _can_manage_embeddings(
        self,
        user,
        document: Document,
    ) -> bool:
        """
        Solo admin y owner pueden generar embeddings
        porque esta operación persiste nueva
        información derivada.
        """

        if self._is_admin(user):
            return True

        return document.owner_id == user.id

    def _can_read_embeddings(
        self,
        user,
        document: Document,
    ) -> bool:
        """
        Reglas de lectura:
        - admin puede ver todo
        - owner puede ver sus embeddings
        - usuario con acceso explícito puede consultar
          la información
        """

        if self._is_admin(user):
            return True

        if document.owner_id == user.id:
            return True

        access = self.document_repo.get_explicit_access(
            document.id,
            user.id,
        )

        return access is not None

    def generate_embeddings_for_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
        model_name: str | None = None,
    ) -> list[DocumentEmbedding]:
        """
        Genera embeddings para todos los chunks de
        una versión concreta y los persiste
        asociados a cada chunk.
        """

        document = self.document_repo.get_document_by_id(
            document_id
        )

        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_manage_embeddings(
            current_user,
            document,
        ):
            raise PermissionError(
                "No tienes permisos para generar embeddings de este documento"
            )

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        chunks = (
            self.embedding_repo.list_chunks_for_version(
                version.id
            )
        )

        if not chunks:
            raise ValueError(
                "No existen chunks para esta versión. Ejecuta antes el chunking de R31"
            )

        provider_result = (
            self.embedding_client.generate_embeddings(
                texts=[chunk.content for chunk in chunks],
                model_name=model_name,
            )
        )

        return (
            self.embedding_repo.replace_embeddings_for_chunks(
                document_id=document.id,
                document_version_id=version.id,
                chunks=chunks,
                vectors=provider_result.vectors,
                model_name=provider_result.model_name,
                provider="mock",
            )
        )

    def get_embeddings_for_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
    ) -> list[DocumentEmbedding]:
        """
        Recupera los embeddings ya guardados para
        una versión concreta.
        """

        document = self.document_repo.get_document_by_id(
            document_id
        )

        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_embeddings(
            current_user,
            document,
        ):
            raise PermissionError(
                "No tienes permisos para consultar los embeddings de este documento"
            )

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )

        if version is None:
            raise ValueError("Versión no encontrada")

        embeddings = (
            self.embedding_repo.list_embeddings_for_version(
                version.id
            )
        )

        if not embeddings:
            raise ValueError(
                "No existen embeddings generados para esta versión"
            )

        return embeddings