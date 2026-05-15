import re

import httpx

from app.core.config import settings


class OpenAIChatClient:
    """
    Cliente básico para generar respuestas con un modelo LLM.

    Si existe API key, llama al proveedor externo.
    Si no existe API key, genera una respuesta local contextual
    usando el prompt construido por el servicio RAG.
    """

    def generate_answer(self, prompt: str) -> str:
        """
        Genera una respuesta a partir de un prompt.

        En entorno local, sin API key, no llama a OpenAI.
        En su lugar, usa el contexto recuperado para devolver
        una respuesta simulada pero coherente con la pregunta.
        """
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError("El prompt no puede estar vacío")

        if not settings.openai_api_key:
            return self._generate_local_answer(clean_prompt)

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.openai_chat_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Responde en español usando únicamente el contexto "
                        "documental proporcionado."
                    ),
                },
                {
                    "role": "user",
                    "content": clean_prompt,
                },
            ],
            "temperature": settings.openai_chat_temperature,
        }

        with httpx.Client(
            timeout=settings.openai_chat_timeout_seconds
        ) as client:
            response = client.post(
                settings.openai_chat_url,
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise ValueError("Error al generar respuesta mediante el LLM")

        data = response.json()
        choices = data.get("choices", [])

        if not choices:
            raise ValueError("El LLM no devolvió ninguna respuesta")

        content = choices[0].get("message", {}).get("content", "").strip()

        if not content:
            raise ValueError("El LLM devolvió una respuesta vacía")

        return content

    def _extract_question_from_prompt(self, prompt: str) -> str:
        """
        Extrae la pregunta del usuario desde el prompt RAG.
        """
        marker = "Pregunta del usuario:"

        if marker not in prompt:
            return ""

        question_block = prompt.split(marker, 1)[1]

        if "Respuesta:" in question_block:
            question_block = question_block.split("Respuesta:", 1)[0]

        return question_block.strip().lower()

    def _extract_context_from_prompt(self, prompt: str) -> str:
        """
        Extrae el bloque de contexto documental desde el prompt.
        """
        start_marker = "Contexto documental:"
        end_marker = "Pregunta del usuario:"

        if start_marker not in prompt:
            return ""

        context_block = prompt.split(start_marker, 1)[1]

        if end_marker in context_block:
            context_block = context_block.split(end_marker, 1)[0]

        return context_block.strip()

    def _clean_context_text(self, text: str) -> str:
        """
        Limpia marcas internas del prompt para obtener texto legible.
        """
        clean_text = re.sub(r"\[Fuente \d+\]", "", text)
        clean_text = re.sub(r"Documento:.*", "", clean_text)
        clean_text = re.sub(r"Chunk:.*", "", clean_text)
        clean_text = clean_text.replace("Contenido:", "")
        clean_text = re.sub(r"\s+", " ", clean_text)

        return clean_text.strip()

    def _generate_local_answer(self, prompt: str) -> str:
        """
        Genera una respuesta local contextual.

        No usa IA real, pero aprovecha el contexto documental
        recuperado para que la respuesta tenga sentido en demo,
        memoria y pruebas funcionales.
        """
        question = self._extract_question_from_prompt(prompt)
        context = self._extract_context_from_prompt(prompt)
        clean_context = self._clean_context_text(context)

        if not clean_context:
            return (
                "No hay información suficiente en el contexto documental "
                "recuperado para responder a la pregunta."
            )

        if "vacaciones" in question and "vacaciones" in clean_context.lower():
            return (
                "Según el contexto documental recuperado, los empleados pueden "
                "solicitar vacaciones mediante el sistema interno, indicando "
                "las fechas de inicio y fin, así como el responsable de "
                "aprobación. El departamento de recursos humanos revisa las "
                "solicitudes teniendo en cuenta la disponibilidad, el calendario "
                "laboral y las necesidades organizativas."
            )

        if (
            ("despido" in question or "contrato" in question)
            and ("despido" in clean_context.lower() or "contrato" in clean_context.lower())
        ):
            return (
                "Según el contexto documental recuperado, la finalización del "
                "contrato puede producirse por baja voluntaria, despido "
                "disciplinario, despido objetivo, acuerdo mutuo o finalización "
                "del contrato temporal. También se contemplan obligaciones "
                "relacionadas con la confidencialidad y la protección de la "
                "información interna de la empresa."
            )

        if "rag" in question or "pipeline" in question or "embeddings" in question:
            return (
                "Según el contexto documental recuperado, Archivum procesa los "
                "documentos mediante extracción de texto, fragmentación en "
                "chunks, generación de embeddings y almacenamiento vectorial. "
                "Después, el flujo RAG recupera fragmentos relevantes, construye "
                "un prompt, genera una respuesta y mantiene trazabilidad mediante "
                "citas documentales y métricas de ejecución."
            )

        return (
            "Según el contexto documental recuperado, "
            f"{clean_context[:450]}"
        )