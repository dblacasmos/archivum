from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_p15_1_metrics_endpoint_is_available():
    """
    P15.1:
    Verifica que el endpoint /metrics responde correctamente
    y expone métricas en formato Prometheus.
    """
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "archivum_http_requests_total" in response.text


def test_p15_1_request_id_header_is_returned():
    """
    P15.1:
    Verifica que la API devuelve un X-Request-ID en la respuesta.
    """
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


def test_p15_1_query_stage_metrics_are_exposed_after_query(setup_editor_user_and_token):
    """
    P15.1:
    Verifica que tras ejecutar /query aparecen métricas
    de las etapas retrieval, embedding y llm.
    """
    access_token = setup_editor_user_and_token()

    query_response = client.post(
        "/query",
        json={"query": "documentación técnica"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert query_response.status_code == 200

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200

    metrics_text = metrics_response.text
    assert 'archivum_rag_stage_total' in metrics_text
    assert 'stage="retrieval"' in metrics_text
    assert 'stage="embedding"' in metrics_text
    assert 'stage="llm"' in metrics_text