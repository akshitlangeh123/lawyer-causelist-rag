from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db.database as database_module
from app.db.database import init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    test_db_path = tmp_path / "test_cause_list.db"

    monkeypatch.setattr(database_module, "DB_PATH", test_db_path)

    init_db()

    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_documents_endpoint_returns_list(client: TestClient) -> None:
    response = client.get("/documents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_cases_endpoint_returns_expected_shape(client: TestClient) -> None:
    response = client.get("/cases?limit=5")

    assert response.status_code == 200

    payload = response.json()

    assert "count" in payload
    assert "results" in payload
    assert isinstance(payload["results"], list)


def test_case_details_endpoint_returns_expected_shape(client: TestClient) -> None:
    response = client.get("/case-details?limit=5")

    assert response.status_code == 200

    payload = response.json()

    assert "count" in payload
    assert "results" in payload
    assert isinstance(payload["results"], list)