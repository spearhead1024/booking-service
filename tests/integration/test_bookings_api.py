import pytest
from fastapi.testclient import TestClient

from tests.conftest import Api
from tests.overlap_cases import day

BOOKINGS = "/api/v1/bookings"


class TestCreateAndGet:
    def test_create_booking_is_confirmed(self, create_booking: Api, property_id: int) -> None:
        response = create_booking(11, 16, guest_name="  Jane Doe ")

        assert response.status_code == 201
        body = response.json()
        assert body == {
            "id": body["id"],
            "property_id": property_id,
            "guest_name": "Jane Doe",
            "start_date": "2030-01-11",
            "end_date": "2030-01-16",
            "status": "CONFIRMED",
        }
        assert response.headers["location"].endswith(f"{BOOKINGS}/{body['id']}")

    def test_get_booking(self, client: TestClient, create_booking: Api) -> None:
        created = create_booking(11, 16).json()

        response = client.get(f"{BOOKINGS}/{created['id']}")

        assert response.status_code == 200
        assert response.json() == created

    def test_get_missing_booking_returns_404(self, client: TestClient) -> None:
        assert client.get(f"{BOOKINGS}/999").status_code == 404

    def test_create_for_missing_property_returns_404(self, create_booking: Api) -> None:
        response = create_booking(11, 16, property_id=999)

        assert response.status_code == 404
        assert response.json()["message"] == "Property 999 not found."

    @pytest.mark.parametrize(("start", "end"), [(16, 11), (11, 11)], ids=["reversed", "same-day"])
    def test_rejects_start_not_before_end(self, create_booking: Api, start: int, end: int) -> None:
        response = create_booking(start, end)

        assert response.status_code == 400
        assert response.json()["error"] == "validation_error"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"guest_name": None},
            {"guest_name": 123},
            {"start_date": "not-a-date"},
            {"start_date": "2030-02-30"},
            {"start_date": 1893456000},
            {"start_date": "2030-01-11T00:00:00"},
            {"property_id": "abc"},
            {"property_id": "1"},
            {"property_id": 1.0},
            {"property_id": True},
            {"property_id": 0},
            {"status": "CANCELED"},
        ],
        ids=[
            "null-guest",
            "numeric-guest",
            "bad-date",
            "impossible-date",
            "timestamp-date",
            "datetime-string",
            "bad-property-id",
            "string-property-id",
            "float-property-id",
            "bool-property-id",
            "zero-property-id",
            "status-not-writable",
        ],
    )
    def test_rejects_malformed_payload(self, create_booking: Api, overrides: dict) -> None:
        assert create_booking(11, 16, **overrides).status_code == 400

    def test_date_order_error_points_at_end_date(self, create_booking: Api) -> None:
        details = create_booking(16, 11).json()["details"]

        assert details == [
            {
                "field": "body.end_date",
                "message": "start_date must be before end_date",
                "type": "date_order",
            }
        ]

    def test_rejects_missing_fields(self, client: TestClient) -> None:
        response = client.post(BOOKINGS, json={})

        assert response.status_code == 400
        fields = {detail["field"] for detail in response.json()["details"]}
        assert fields == {"body.property_id", "body.guest_name", "body.start_date", "body.end_date"}


class TestList:
    def test_filters_and_paginates(
        self, client: TestClient, create_booking: Api, property_id: int
    ) -> None:
        first = create_booking(1, 3).json()
        second = create_booking(5, 7).json()
        create_booking(9, 10)
        client.post(f"{BOOKINGS}/{second['id']}/cancel")
        other_property = client.post(
            "/api/v1/properties", json={"name": "Other", "country_code": "ES"}
        ).json()["id"]
        create_booking(1, 3, property_id=other_property)

        page = client.get(BOOKINGS, params={"property_id": property_id, "limit": 2}).json()
        assert page["total"] == 3
        assert [b["id"] for b in page["items"]] == [first["id"], second["id"]]

        canceled = client.get(BOOKINGS, params={"status": "CANCELED"}).json()
        assert [b["id"] for b in canceled["items"]] == [second["id"]]

        assert client.get(BOOKINGS).json()["total"] == 4

    def test_filter_by_missing_property_returns_404(self, client: TestClient) -> None:
        assert client.get(BOOKINGS, params={"property_id": 999}).status_code == 404

    @pytest.mark.parametrize(
        "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"status": "PENDING"}]
    )
    def test_rejects_invalid_query(self, client: TestClient, params: dict) -> None:
        assert client.get(BOOKINGS, params=params).status_code == 400


class TestUpdate:
    def test_updates_guest_name_only(self, client: TestClient, create_booking: Api) -> None:
        booking = create_booking(11, 16).json()

        response = client.patch(f"{BOOKINGS}/{booking['id']}", json={"guest_name": "John"})

        assert response.status_code == 200
        assert response.json() == {**booking, "guest_name": "John"}

    def test_moving_within_own_range_is_not_a_conflict(
        self, client: TestClient, create_booking: Api
    ) -> None:
        booking = create_booking(11, 16).json()

        response = client.patch(
            f"{BOOKINGS}/{booking['id']}", json={"start_date": day(12).isoformat()}
        )

        assert response.status_code == 200
        assert response.json()["start_date"] == "2030-01-12"

    def test_update_into_another_booking_returns_409(
        self, client: TestClient, create_booking: Api
    ) -> None:
        create_booking(11, 16)
        booking = create_booking(20, 25).json()

        response = client.patch(
            f"{BOOKINGS}/{booking['id']}", json={"start_date": day(16).isoformat()}
        )

        assert response.status_code == 409
        assert response.json()["error"] == "date_overlap"
        assert client.get(f"{BOOKINGS}/{booking['id']}").json() == booking  # unchanged

    def test_partial_date_update_is_validated_against_stored_date(
        self, client: TestClient, create_booking: Api
    ) -> None:
        booking = create_booking(11, 16).json()

        response = client.patch(
            f"{BOOKINGS}/{booking['id']}", json={"start_date": day(20).isoformat()}
        )

        assert response.status_code == 400
        assert response.json()["message"] == "start_date must be before end_date"

    def test_canceled_booking_can_move_onto_taken_dates(
        self, client: TestClient, create_booking: Api
    ) -> None:
        create_booking(11, 16)
        booking = create_booking(20, 25).json()
        client.post(f"{BOOKINGS}/{booking['id']}/cancel")

        response = client.patch(
            f"{BOOKINGS}/{booking['id']}", json={"start_date": day(12).isoformat()}
        )

        assert response.status_code == 200  # canceled bookings hold no dates

    def test_empty_update_returns_400(self, client: TestClient, create_booking: Api) -> None:
        booking = create_booking(11, 16).json()

        response = client.patch(f"{BOOKINGS}/{booking['id']}", json={})

        assert response.status_code == 400
        assert response.json()["details"][0]["type"] == "empty_update"

    def test_update_missing_booking_returns_404(self, client: TestClient) -> None:
        assert client.patch(f"{BOOKINGS}/999", json={"guest_name": "X"}).status_code == 404


class TestCancelAndRebook:
    def test_cancel_releases_dates(self, client: TestClient, create_booking: Api) -> None:
        booking = create_booking(11, 16).json()

        response = client.post(f"{BOOKINGS}/{booking['id']}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELED"
        assert create_booking(11, 16).status_code == 201

    def test_cancel_twice_returns_409(self, client: TestClient, create_booking: Api) -> None:
        booking = create_booking(11, 16).json()
        client.post(f"{BOOKINGS}/{booking['id']}/cancel")

        response = client.post(f"{BOOKINGS}/{booking['id']}/cancel")

        assert response.status_code == 409
        assert response.json()["error"] == "invalid_state"

    def test_rebook_when_dates_free(self, client: TestClient, create_booking: Api) -> None:
        booking = create_booking(11, 16).json()
        client.post(f"{BOOKINGS}/{booking['id']}/cancel")

        response = client.post(f"{BOOKINGS}/{booking['id']}/rebook")

        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMED"

    def test_rebook_when_dates_taken_returns_409(
        self, client: TestClient, create_booking: Api
    ) -> None:
        booking = create_booking(11, 16).json()
        client.post(f"{BOOKINGS}/{booking['id']}/cancel")
        taker = create_booking(16, 18).json()

        response = client.post(f"{BOOKINGS}/{booking['id']}/rebook")

        assert response.status_code == 409
        assert response.json()["details"]["conflict_id"] == taker["id"]
        assert client.get(f"{BOOKINGS}/{booking['id']}").json()["status"] == "CANCELED"

    def test_rebook_confirmed_booking_returns_409(
        self, client: TestClient, create_booking: Api
    ) -> None:
        booking = create_booking(11, 16).json()

        response = client.post(f"{BOOKINGS}/{booking['id']}/rebook")

        assert response.status_code == 409
        assert response.json()["error"] == "invalid_state"

    @pytest.mark.parametrize("action", ["cancel", "rebook"])
    def test_action_on_missing_booking_returns_404(self, client: TestClient, action: str) -> None:
        assert client.post(f"{BOOKINGS}/999/{action}").status_code == 404


class TestDelete:
    def test_delete_removes_booking_and_frees_dates(
        self, client: TestClient, create_booking: Api
    ) -> None:
        booking = create_booking(11, 16).json()

        response = client.delete(f"{BOOKINGS}/{booking['id']}")

        assert response.status_code == 204
        assert response.content == b""
        assert client.get(f"{BOOKINGS}/{booking['id']}").status_code == 404
        assert create_booking(11, 16).status_code == 201

    def test_delete_missing_booking_returns_404(self, client: TestClient) -> None:
        assert client.delete(f"{BOOKINGS}/999").status_code == 404
