from app.documents.embeddings import EmbeddingProviderResult, OpenAIEmbeddingClient
from app.rag.llm_client import OpenAIChatClient
from test_r70_basic_rag import (
    build_sparse_vector,
    create_user_with_role,
    login_and_get_token,
    prepare_document_for_rag,
    reset_database_for_r70,
    client,
)
from app.core.config import settings


def fake_r71_embedding(
    self,
    texts: list[str],
    model_name: str | None = None,
) -> EmbeddingProviderResult:
    """
    Genera embeddings falsos y controlados.

    Así la prueba no depende de OpenAI ni de internet,
    porque bastante drama hay ya con pytest.
    """
    final_model_name = model_name or settings.openai_embeddings_model
    fake_vectors: list[list[float]] = []

    for text_value in texts:
        normalized_text = text_value.lower()

        if "contrato" in normalized_text or "laboral" in normalized_text:
            fake_vectors.append(build_sparse_vector(0))
        elif "auditoría" in normalized_text:
            fake_vectors.append(build_sparse_vector(1))
        else:
            fake_vectors.append(build_sparse_vector(2))

    return EmbeddingProviderResult(
        model_name=final_model_name,
        vectors=fake_vectors,
    )


def fake_supported_llm_answer(self, prompt: str) -> str:
    """
    Simula una respuesta apoyada en el contexto recuperado.
    """
    assert "Contrato laboral autorizado" in prompt

    return (
        "El contrato laboral autorizado incluye cláusulas laborales "
        "y condiciones de trabajo."
    )


def fake_hallucinated_llm_answer(self, prompt: str) -> str:
    """
    Simula una respuesta inventada.

    El contexto habla de contrato laboral, pero esta respuesta mete
    información fiscal que no aparece en los chunks.
    """
    assert "Contrato laboral autorizado" in prompt

    return (
        "El documento establece una deducción fiscal internacional "
        "del 35 por ciento aplicable a inversiones extranjeras."
    )


def test_p71_1_accepts_answer_when_it_is_supported_by_context(monkeypatch):
    """
    P71.1 - Acepta una respuesta cuando está apoyada en el contexto.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r71_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_supported_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r71_ok@test.com",
        password="editor123",
        display_name="Usuario R71 OK",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r71_ok@test.com",
        password="editor123",
    )

    prepare_document_for_rag(
        token=token,
        title="Contrato laboral autorizado",
        content=(
            "Contrato laboral autorizado con cláusulas laborales, "
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

    assert data["answer_status"] == "generated"
    assert data["fallback_applied"] is False
    assert data["hallucination_checks"]["enabled"] is True
    assert data["hallucination_checks"]["is_valid"] is True
    assert data["used_context_chunks"] <= 5
    assert "cláusulas laborales" in data["answer"]


def test_p71_1_applies_fallback_when_answer_is_not_supported(monkeypatch):
    """
    P71.1 - Aplica fallback si la respuesta no está fundamentada.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r71_embedding,
    )

    monkeypatch.setattr(
        OpenAIChatClient,
        "generate_answer",
        fake_hallucinated_llm_answer,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r71_fallback@test.com",
        password="editor123",
        display_name="Usuario R71 Fallback",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r71_fallback@test.com",
        password="editor123",
    )

    prepare_document_for_rag(
        token=token,
        title="Contrato laboral autorizado",
        content=(
            "Contrato laboral autorizado con cláusulas laborales, "
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

    assert data["answer_status"] == "fallback"
    assert data["fallback_applied"] is True
    assert data["hallucination_checks"]["enabled"] is True
    assert data["hallucination_checks"]["is_valid"] is False
    assert "No hay información suficiente" in data["answer"]
    assert "deducción fiscal internacional" not in data["answer"]


def test_p71_1_applies_fallback_when_no_context_is_retrieved(monkeypatch):
    """
    P71.1 - Aplica fallback si no se recupera contexto documental.
    """
    monkeypatch.setattr(
        OpenAIEmbeddingClient,
        "generate_embeddings",
        fake_r71_embedding,
    )

    reset_database_for_r70()

    create_user_with_role(
        email="rag_r71_empty@test.com",
        password="editor123",
        display_name="Usuario R71 Sin Contexto",
        role_name="editor",
    )

    token = login_and_get_token(
        email="rag_r71_empty@test.com",
        password="editor123",
    )

    response = client.post(
        "/rag",
        json={
            "query": "contrato laboral",
            "limit": 5,
            "search_mode": "hybrid",
            "metadata_filters": {"category": "inexistente"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["retrieved_chunks"] == 0
    assert data["used_context_chunks"] == 0
    assert data["answer_status"] == "fallback"
    assert data["fallback_applied"] is True
    assert data["hallucination_checks"]["is_valid"] is False
    assert "No hay información suficiente" in data["answer"]