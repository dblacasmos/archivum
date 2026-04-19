import re
from dataclasses import dataclass
from pathlib import Path

import fitz
from docx import Document as DocxDocument

from app.documents.models import DocumentVersion


@dataclass
class TextExtractionResult:
    """
    Resultado simple del proceso de extracción.
    """

    extracted_text: str
    source_type: str
    characters_count: int


class TextExtractionService:
    """
    Servicio responsable de extraer texto desde una versión de documento.

    Este servicio NO hace chunking.
    Este servicio NO genera embeddings.
    Este servicio solo convierte una versión documental
    en texto plano reutilizable.
    """

    def _normalize_text(self, text: str) -> str:
        """
        Limpia saltos de línea y espacios para guardar
        un texto más consistente en base de datos.
        """
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _extract_from_plain_text_file(self, file_path: Path) -> str:
        """
        Lee archivos de texto plano probando varias codificaciones
        habituales para evitar fallos innecesarios.
        """
        file_bytes = file_path.read_bytes()

        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        raise ValueError("No se ha podido decodificar el archivo de texto")

    def _extract_from_pdf(self, file_path: Path) -> str:
        """
        Extrae texto desde un PDF usando PyMuPDF.
        """
        fragments: list[str] = []

        with fitz.open(file_path) as pdf_document:
            for page in pdf_document:
                fragments.append(page.get_text("text"))

        return "\n".join(fragments)

    def _extract_from_docx(self, file_path: Path) -> str:
        """
        Extrae texto desde un archivo DOCX.
        """
        docx_document = DocxDocument(str(file_path))
        fragments: list[str] = []

        for paragraph in docx_document.paragraphs:
            if paragraph.text and paragraph.text.strip():
                fragments.append(paragraph.text)

        return "\n".join(fragments)

    def extract_from_version(self, version: DocumentVersion) -> TextExtractionResult:
        """
        Extrae texto desde una versión concreta.

        Casos soportados:
        - versión creada desde contenido textual directo
        - .txt
        - .md
        - .pdf
        - .docx
        """
        # Si la versión ya nació como texto puro, no hace falta tocar disco.
        if version.content is not None and version.content.strip():
            normalized_text = self._normalize_text(version.content)

            if not normalized_text:
                raise ValueError("La versión no contiene texto útil para extraer")

            return TextExtractionResult(
                extracted_text=normalized_text,
                source_type="inline_text",
                characters_count=len(normalized_text),
            )

        # Si no hay contenido inline, necesitamos un archivo físico asociado.
        if version.storage_path is None or not version.storage_path.strip():
            raise ValueError("La versión no tiene contenido ni archivo asociado")

        file_path = Path(version.storage_path)

        if not file_path.exists():
            raise ValueError("El archivo físico asociado a la versión no existe")

        extension = file_path.suffix.lower()

        if extension in {".txt", ".md"}:
            raw_text = self._extract_from_plain_text_file(file_path)
            source_type = "plain_text_file"
        elif extension == ".pdf":
            raw_text = self._extract_from_pdf(file_path)
            source_type = "pdf"
        elif extension == ".docx":
            raw_text = self._extract_from_docx(file_path)
            source_type = "docx"
        elif extension == ".doc":
            raise ValueError(
                "La extracción de archivos .doc no está soportada todavía. Usa .docx o PDF."
            )
        else:
            raise ValueError(f"No existe extractor configurado para la extensión {extension}")

        normalized_text = self._normalize_text(raw_text)

        if not normalized_text:
            raise ValueError("No se ha podido extraer texto útil del documento")

        return TextExtractionResult(
            extracted_text=normalized_text,
            source_type=source_type,
            characters_count=len(normalized_text),
        )