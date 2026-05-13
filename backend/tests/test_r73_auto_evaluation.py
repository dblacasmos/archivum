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


def fake_r73_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Genera embeddings falsos para que la prueba sea estable.

    Así evitamos depender de OpenAI durante el test. Porque pagar APIs
    para comprobar una palabra sería otra obra maestra humana.
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "contrato" in normalized_text or "laboral" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        else:
            fake_vectors.append(build_sparse_vector(1))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def fake_r73_llm_answer(self, prompt: str) -> str:
    """
    Simula una respuesta generada usando el contexto documental.
    """
    assert "[Fuente 1]" in prompt
    assert "Contrato laboral evaluable" in prompt

    return (
        "El contrato laboral evaluable incluye cláusulas laborales, "
        "condiciones de trabajo y obligaciones básicas."
    )


def test_p73_1_rag_response_includes_auto_evaluation(monkeypatch):
    """
    P73.1 - Comprueba que la respuesta RAG incluye evaluación automática.

    La prueba valida:
    - que la evaluación está activa
    - que se calculan métricas básicas
    - que el resultado es coherente con una respuesta apoyada en contexto
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r73_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_r73_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r73@test.com",
        password="editor123",
        display_name="Usuario R73",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r73@test.com",
        password="editor123",
    )

    prepare_document_for_rag(
        token=token,
        title="Contrato laboral evaluable",
        content=(
            "Contrato laboral evaluable con cláusulas laborales, "
            "condiciones de trabajo y obligaciones básicas."
        ),
        metadata={"category": "laboral"},
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato laboral",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "laboral"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()
    evaluation = data["evaluation"]

    assert data["answer_status"] == "generated"
    assert data["debug"]["evaluation_enabled"] is True
    assert data["debug"]["rag_version"] == "basic_r74_latency_cost_metrics"
    assert data["debug"]["usage_metrics_enabled"] is True
    assert "usage_metrics" in data

    assert evaluation["enabled"] is True
    assert evaluation["verdict"] in ["good", "acceptable"]
    assert evaluation["overall_score"] > 0
    assert evaluation["coherence_score"] > 0
    assert evaluation["relevance_score"] > 0
    assert evaluation["context_overlap_score"] > 0
    assert evaluation["citation_coverage_score"] == 1.0

    assert evaluation["metrics"]["context_chunks_count"] == data["used_context_chunks"]
    assert evaluation["metrics"]["citations_count"] == len(data["citations"])
    assert evaluation["metrics"]["answer_status"] == "generated"

    assert "Evaluación" in evaluation["explanation"]