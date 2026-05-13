from app.core.config import settings
from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.rag.llm_client import OpenAIChatClient
from test_r70_basic_rag import (
    build_sparse_vector,
    client,
    create_user_with_role,
    login_and_get_token,
    prepare_document_for_rag,
    reset_database_for_r70,
)


def fake_r74_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Genera embeddings falsos para que la prueba sea repetible.

    Así no se llama a OpenAI durante el test. Porque quemar dinero
    para probar una métrica aproximada sería poesía administrativa.
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "contrato" in normalized_text or "coste" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        else:
            fake_vectors.append(build_sparse_vector(1))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def fake_r74_llm_answer(self, prompt: str) -> str:
    """
    Simula una respuesta del LLM usando el contexto recuperado.
    """
    assert "[Fuente 1]" in prompt
    assert "Contrato laboral con coste medible" in prompt

    return (
        "El contrato laboral con coste medible permite analizar "
        "la latencia y el coste básico de una consulta RAG."
    )


def test_p74_1_rag_response_includes_latency_and_cost_metrics(monkeypatch):
    """
    P74.1 - Comprueba que el endpoint /rag devuelve métricas de latencia y coste.

    La prueba valida:
    - que las métricas están activas
    - que existen tiempos de ejecución
    - que se estiman tokens
    - que se calcula un coste básico
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r74_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_r74_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r74@test.com",
        password="editor123",
        display_name="Usuario R74",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r74@test.com",
        password="editor123",
    )

    prepare_document_for_rag(
        token=token,
        title="Contrato laboral con coste medible",
        content=(
            "Contrato laboral con coste medible para analizar "
            "latencia, tiempos de respuesta y coste básico de consultas RAG."
        ),
        metadata={"category": "laboral"},
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato coste latencia",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "laboral"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()
    usage_metrics = data["usage_metrics"]

    assert data["debug"]["rag_version"] == "basic_r74_latency_cost_metrics"
    assert data["debug"]["evaluation_enabled"] is True
    assert data["debug"]["usage_metrics_enabled"] is True
    assert "evaluation" in data
    assert "usage_metrics" in data

    assert usage_metrics["enabled"] is True
    assert usage_metrics["total_latency_ms"] >= 0
    assert usage_metrics["retrieval_latency_ms"] >= 0
    assert usage_metrics["llm_latency_ms"] >= 0

    assert usage_metrics["prompt_tokens_estimated"] > 0
    assert usage_metrics["answer_tokens_estimated"] > 0
    assert usage_metrics["total_tokens_estimated"] == (
        usage_metrics["prompt_tokens_estimated"]
        + usage_metrics["answer_tokens_estimated"]
    )

    assert usage_metrics["estimated_cost_eur"] >= 0
    assert usage_metrics["cost_model"] == "estimacion_academica_basica"
    assert "Métricas RAG" in usage_metrics["explanation"]