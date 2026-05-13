import httpx

from app.core.config import settings


class OpenAIChatClient:
    """
    Cliente básico para generar respuestas con un modelo LLM.

    Se separa en una clase propia para que el servicio RAG no tenga
    que conocer detalles HTTP del proveedor externo.
    """

    def generate_answer(self, prompt: str) -> str:
        """
        Genera una respuesta a partir de un prompt.

        Si no hay API key configurada, devuelve una respuesta local
        para permitir desarrollo y pruebas sin depender de OpenAI.
        """
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError("El prompt no puede estar vacío")

        if not settings.openai_api_key:
            return self._generate_local_answer()

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

    def _generate_local_answer(self) -> str:
        """
        Respuesta local usada cuando no hay API key.

        No simula inteligencia real. Simula que el proyecto no explota,
        que ya es más de lo que muchas APIs consiguen un lunes.
        """
        return (
            "Respuesta generada en modo local a partir del contexto "
            "documental recuperado por el sistema."
        )