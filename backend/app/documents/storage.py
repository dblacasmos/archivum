import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


@dataclass
class StoredFileInfo:
    """
    Resultado de guardar un archivo en disco.
    """

    original_filename: str
    stored_filename: str
    storage_path: str
    mime_type: str | None
    size_bytes: int


class DocumentStorageService:
    """
    Servicio responsable del almacenamiento físico de archivos.

    Su responsabilidad es muy concreta:
    - validar extensión
    - validar tamaño
    - generar un nombre seguro
    - guardar el archivo en disco

    No procesa el contenido ni extrae texto.
    """

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or settings.upload_dir)

    def _sanitize_filename(self, filename: str) -> str:
        """
        Limpia el nombre del archivo para evitar rutas raras
        o caracteres problemáticos.
        """
        safe_name = Path(filename).name
        safe_name = safe_name.strip().replace(" ", "_")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "", safe_name)

        if not safe_name:
            raise ValueError("El nombre del archivo no es válido")

        return safe_name

    def _validate_extension(self, filename: str) -> str:
        """
        Comprueba que la extensión esté permitida.
        """
        extension = Path(filename).suffix.lower()

        if extension not in settings.get_allowed_upload_extensions():
            raise ValueError("La extensión del archivo no está permitida")

        return extension

    async def save_upload(self, upload_file: UploadFile, owner_id: str) -> StoredFileInfo:
        """
        Guarda el archivo subido en disco dentro de una carpeta
        asociada al usuario propietario.
        """
        if upload_file.filename is None or not upload_file.filename.strip():
            raise ValueError("Debes enviar un archivo con nombre válido")

        safe_original_filename = self._sanitize_filename(upload_file.filename)
        self._validate_extension(safe_original_filename)

        file_bytes = await upload_file.read()

        if not file_bytes:
            raise ValueError("El archivo está vacío")

        if len(file_bytes) > settings.max_upload_size_bytes:
            raise ValueError("El archivo supera el tamaño máximo permitido")

        user_dir = self.base_dir / str(owner_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid.uuid4().hex}_{safe_original_filename}"
        final_path = user_dir / stored_filename

        final_path.write_bytes(file_bytes)

        return StoredFileInfo(
            original_filename=safe_original_filename,
            stored_filename=stored_filename,
            storage_path=str(final_path),
            mime_type=upload_file.content_type,
            size_bytes=len(file_bytes),
        )