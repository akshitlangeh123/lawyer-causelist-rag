from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_documents_endpoint_returns_list() -> None:
    response = client.get("/documents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_cases_endpoint_returns_expected_shape() -> None:
    response = client.get("/cases?limit=5")

    assert response.status_code == 200

    payload = response.json()

    assert "count" in payload
    assert "results" in payload
    assert isinstance(payload["results"], list)


def test_case_details_endpoint_returns_expected_shape() -> None:
    response = client.get("/case-details?limit=5")

    assert response.status_code == 200

    payload = response.json()

    assert "count" in payload
    assert "results" in payload
    assert isinstance(payload["results"], list)
