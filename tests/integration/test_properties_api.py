import pytest
from fastapi.testclient import TestClient


def test_create_and_get_property(client: TestClient) -> None:
    created = client.post("/api/v1/properties", json={"name": "Cabin", "country_code": "fr"})

    assert created.status_code == 201
    body = created.json()
    assert body == {"id": body["id"], "name": "Cabin", "country_code": "FR"}
    assert created.headers["location"].endswith(f"/api/v1/properties/{body['id']}")

    fetched = client.get(f"/api/v1/properties/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_get_missing_property_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/properties/999")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {"country_code": "PT"},
        {"name": "Cabin"},
        {"name": "", "country_code": "PT"},
        {"name": "Cabin", "country_code": "Portugal"},
        {"name": "Cabin", "country_code": "PT", "owner": "me"},
    ],
    ids=["missing-name", "missing-country", "blank-name", "bad-country", "unknown-field"],
)
def test_create_property_rejects_invalid_payload(client: TestClient, payload: dict) -> None:
    response = client.post("/api/v1/properties", json=payload)

    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"
