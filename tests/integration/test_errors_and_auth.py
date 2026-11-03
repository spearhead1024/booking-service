from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

API_KEY = "s3cret-key"


@pytest.fixture
def secured_client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings.model_copy(update={"api_key": SecretStr(API_KEY)}))
    with TestClient(app) as test_client:
        yield test_client


class TestErrorFormat:
    def test_unknown_route_uses_error_format(self, client: TestClient) -> None:
        response = client.get("/api/v1/nowhere")

        assert response.status_code == 404
        assert response.json() == {"error": "not_found", "message": "Not Found", "details": None}

    def test_wrong_method_returns_405(self, client: TestClient) -> None:
        response = client.put("/api/v1/properties/1", json={})

        assert response.status_code == 405
        assert response.json()["error"] == "method_not_allowed"

    def test_malformed_json_returns_400(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/bookings", content=b"{not json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
        assert response.json()["error"] == "validation_error"

    def test_non_numeric_path_id_returns_400(self, client: TestClient) -> None:
        assert client.get("/api/v1/bookings/abc").status_code == 400

    def test_unexpected_error_hides_internals(self, settings: Settings) -> None:
        app = create_app(settings)

        @app.get("/boom")
        def boom() -> None:
            raise RuntimeError("database password is hunter2")

        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/boom")

        assert response.status_code == 500
        assert response.json() == {
            "error": "internal_error",
            "message": "An unexpected error occurred.",
            "details": None,
        }
        assert "hunter2" not in response.text


class TestApiKeyAuth:
    @pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}], ids=["missing", "wrong"])
    def test_rejects_missing_or_wrong_key(self, secured_client: TestClient, headers: dict) -> None:
        response = secured_client.get("/api/v1/bookings", headers=headers)

        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    def test_accepts_valid_key(self, secured_client: TestClient) -> None:
        response = secured_client.get("/api/v1/bookings", headers={"X-API-Key": API_KEY})

        assert response.status_code == 200

    def test_health_is_public(self, secured_client: TestClient) -> None:
        assert secured_client.get("/health").status_code == 200

    def test_auth_disabled_when_no_key_configured(self, client: TestClient) -> None:
        assert client.get("/api/v1/bookings").status_code == 200


class TestOutOfRangeInput:
    """IDs beyond the 64-bit range cannot exist; they must be a 400, not a driver crash."""

    HUGE = 2**63

    @pytest.mark.parametrize(
        "path",
        [
            f"/api/v1/properties/{HUGE}",
            f"/api/v1/bookings/{HUGE}",
            f"/api/v1/blocks/{HUGE}",
            f"/api/v1/bookings?property_id={HUGE}",
            f"/api/v1/blocks?property_id={HUGE}",
            f"/api/v1/bookings?offset={HUGE}",
        ],
    )
    def test_huge_integers_in_url_return_400(self, client: TestClient, path: str) -> None:
        assert client.get(path).status_code == 400

    def test_huge_property_id_in_body_returns_400(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/bookings",
            json={
                "property_id": self.HUGE,
                "guest_name": "A",
                "start_date": "2030-01-01",
                "end_date": "2030-01-02",
            },
        )

        assert response.status_code == 400

    def test_largest_valid_id_is_a_plain_404(self, client: TestClient) -> None:
        assert client.get(f"/api/v1/bookings/{self.HUGE - 1}").status_code == 404
