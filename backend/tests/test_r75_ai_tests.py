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


def fake_r75_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Genera embeddings falsos para validar el bloque completo de IA.

    La prueba no debe depender de OpenAI ni de internet. Un test que falla
    porque una API externa tiene sueño no valida nada, solo molesta.
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "contrato" in normalized_text or "laboral" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "métrica" in normalized_text or "latencia" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def fake_r75_valid_llm_answer(self, prompt: str) -> str:
    """
    Simula una respuesta correcta del LLM basada en el contexto recuperado.
    """
    assert "[Fuente 1]" in prompt
    assert "Contrato laboral integral IA" in prompt

    return (
        "El contrato laboral integral IA incluye cláusulas laborales, "
        "condiciones de trabajo y obligaciones básicas del documento."
    )


def fake_r75_hallucinated_llm_answer(self, prompt: str) -> str:
    """
    Simula una respuesta inventada para comprobar el control de alucinaciones.
    """
    assert "[Fuente 1]" in prompt

    return (
        "El documento permite solicitar una deducción fiscal internacional "
        "para maquinaria industrial importada desde otro país."
    )


def test_p75_1_end_to_end_rag_retrieval_generation_and_citations(monkeypatch):
    """
    P75.1 - Prueba end-to-end: consulta, retrieval, generación y respuesta con citas.

    Valida que el flujo completo:
    - recupera contexto documental
    - genera una respuesta
    - devuelve citas asociadas a los chunks usados
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r75_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_r75_valid_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r75_e2e@test.com",
        password="editor123",
        display_name="Usuario R75 E2E",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r75_e2e@test.com",
        password="editor123",
    )

    document = prepare_document_for_rag(
        token=token,
        title="Contrato laboral integral IA",
        content=(
            "Contrato laboral integral IA con cláusulas laborales, "
            "condiciones de trabajo y obligaciones básicas del empleado."
        ),
        metadata={"category": "laboral"},
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato laboral integral",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "laboral"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["message"] == "Flujo RAG procesado correctamente"
    assert data["answer_status"] == "generated"
    assert data["fallback_applied"] is False

    assert data["retrieved_chunks"] >= 1
    assert data["used_context_chunks"] >= 1
    assert data["context"][0]["document_id"] == document["id"]

    assert data["answer"]
    assert "contrato laboral" in data["answer"].lower()

    assert data["citations"]
    assert len(data["citations"]) == data["used_context_chunks"]
    assert data["citations"][0]["document_id"] == document["id"]
    assert data["citations"][0]["document_title"] == "Contrato laboral integral IA"


def test_p75_2_hallucination_control_and_citations_work_together(monkeypatch):
    """
    P75.2 - Valida conjuntamente control de alucinaciones y citas.

    Aunque el LLM invente una respuesta, el sistema debe:
    - detectar la falta de apoyo en el contexto
    - aplicar fallback
    - conservar las citas del contexto usado
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r75_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_r75_hallucinated_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r75_guard@test.com",
        password="editor123",
        display_name="Usuario R75 Guard",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r75_guard@test.com",
        password="editor123",
    )

    document = prepare_document_for_rag(
        token=token,
        title="Contrato laboral integral IA",
        content=(
            "Contrato laboral integral IA con cláusulas laborales, "
            "condiciones de trabajo y obligaciones básicas del empleado."
        ),
        metadata={"category": "laboral"},
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato laboral integral",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "laboral"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["answer_status"] == "fallback"
    assert data["fallback_applied"] is True

    assert data["hallucination_checks"]["enabled"] is True
    assert data["hallucination_checks"]["is_valid"] is False
    assert data["hallucination_checks"]["fallback_applied"] is True

    assert "No hay información suficiente" in data["answer"]
    assert "deducción fiscal internacional" not in data["answer"]

    assert data["citations"]
    assert data["citations"][0]["document_id"] == document["id"]
    assert data["citations"][0]["document_title"] == "Contrato laboral integral IA"


def test_p75_3_complete_rag_execution_registers_evaluation_and_usage_metrics(monkeypatch):
    """
    P75.3 - Verifica evaluación automática y métricas durante una ejecución completa.

    La prueba comprueba que el endpoint /rag devuelve:
    - evaluación automática
    - métricas de latencia
    - estimación de tokens
    - estimación básica de coste
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r75_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_r75_valid_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r75_metrics@test.com",
        password="editor123",
        display_name="Usuario R75 Metrics",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r75_metrics@test.com",
        password="editor123",
    )

    prepare_document_for_rag(
        token=token,
        title="Contrato laboral integral IA",
        content=(
            "Contrato laboral integral IA con cláusulas laborales, "
            "condiciones de trabajo y obligaciones básicas del empleado."
        ),
        metadata={"category": "laboral"},
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato laboral integral",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "laboral"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()
    evaluation = data["evaluation"]
    usage_metrics = data["usage_metrics"]

    assert data["debug"]["rag_version"] == "basic_r74_latency_cost_metrics"
    assert data["debug"]["citations_enabled"] is True
    assert data["debug"]["hallucination_control_enabled"] is True
    assert data["debug"]["evaluation_enabled"] is True
    assert data["debug"]["usage_metrics_enabled"] is True

    assert evaluation["enabled"] is True
    assert evaluation["overall_score"] > 0
    assert evaluation["citation_coverage_score"] == 1.0
    assert evaluation["metrics"]["citations_count"] == len(data["citations"])

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