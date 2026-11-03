"""The spec's overlap table, exercised end to end against the database query."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Api
from tests.overlap_cases import ALL_CASES, EXISTING, OverlapCase, day


def _assert_outcome(response_status: int, case: OverlapCase) -> None:
    assert response_status == (409 if case.overlaps else 201)


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_new_booking_vs_existing_booking(create_booking: Api, case: OverlapCase) -> None:
    assert create_booking(*EXISTING).status_code == 201

    _assert_outcome(create_booking(case.start, case.end).status_code, case)


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_new_booking_vs_existing_block(
    create_booking: Api, create_block: Api, case: OverlapCase
) -> None:
    assert create_block(*EXISTING).status_code == 201

    response = create_booking(case.start, case.end)

    _assert_outcome(response.status_code, case)
    if case.overlaps:
        assert response.json()["details"]["conflict_type"] == "block"


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_updated_booking_vs_existing_booking(
    client: TestClient, create_booking: Api, case: OverlapCase
) -> None:
    create_booking(*EXISTING)
    other = create_booking(25, 28).json()

    response = client.patch(
        f"/api/v1/bookings/{other['id']}",
        json={"start_date": day(case.start).isoformat(), "end_date": day(case.end).isoformat()},
    )

    assert response.status_code == (409 if case.overlaps else 200)


def test_bookings_on_different_properties_never_conflict(
    client: TestClient, create_booking: Api
) -> None:
    other_property = client.post(
        "/api/v1/properties", json={"name": "Other", "country_code": "ES"}
    ).json()["id"]
    create_booking(*EXISTING)

    assert create_booking(*EXISTING, property_id=other_property).status_code == 201


def test_conflict_response_is_structured(create_booking: Api) -> None:
    existing = create_booking(*EXISTING).json()

    response = create_booking(12, 14)

    assert response.status_code == 409
    assert response.json() == {
        "error": "date_overlap",
        "message": "The requested dates overlap an existing booking.",
        "details": {
            "conflict_type": "booking",
            "conflict_id": existing["id"],
            "start_date": "2030-01-11",
            "end_date": "2030-01-16",
        },
    }
