from fastapi.testclient import TestClient

from tests.conftest import Api
from tests.overlap_cases import day

BLOCKS = "/api/v1/blocks"


def test_create_get_and_list_blocks(
    client: TestClient, create_block: Api, property_id: int
) -> None:
    created = create_block(11, 16)

    assert created.status_code == 201
    block = created.json()
    assert block == {
        "id": block["id"],
        "property_id": property_id,
        "start_date": "2030-01-11",
        "end_date": "2030-01-16",
    }
    assert client.get(f"{BLOCKS}/{block['id']}").json() == block

    listing = client.get(BLOCKS, params={"property_id": property_id}).json()
    assert listing == {"items": [block], "total": 1, "limit": 50, "offset": 0}


def test_list_blocks_for_missing_property_returns_404(client: TestClient) -> None:
    assert client.get(BLOCKS, params={"property_id": 999}).status_code == 404


def test_create_block_for_missing_property_returns_404(create_block: Api) -> None:
    assert create_block(11, 16, property_id=999).status_code == 404


def test_create_block_rejects_reversed_dates(create_block: Api) -> None:
    assert create_block(16, 11).status_code == 400


def test_overlapping_blocks_are_allowed(create_block: Api) -> None:
    create_block(11, 16)

    assert create_block(14, 20).status_code == 201


def test_block_cannot_cover_confirmed_booking(create_block: Api, create_booking: Api) -> None:
    booking = create_booking(11, 16).json()

    response = create_block(16, 20)

    assert response.status_code == 409
    assert response.json()["details"]["conflict_type"] == "booking"
    assert response.json()["details"]["conflict_id"] == booking["id"]


def test_block_can_cover_canceled_booking(
    client: TestClient, create_block: Api, create_booking: Api
) -> None:
    booking = create_booking(11, 16).json()
    client.post(f"/api/v1/bookings/{booking['id']}/cancel")

    assert create_block(11, 16).status_code == 201


def test_update_block_dates(client: TestClient, create_block: Api, create_booking: Api) -> None:
    block = create_block(11, 16).json()

    response = client.patch(f"{BLOCKS}/{block['id']}", json={"end_date": day(13).isoformat()})

    assert response.status_code == 200
    assert response.json()["end_date"] == "2030-01-13"
    assert create_booking(14, 16).status_code == 201  # freed days are bookable


def test_update_block_onto_booking_returns_409(
    client: TestClient, create_block: Api, create_booking: Api
) -> None:
    create_booking(20, 22)
    block = create_block(11, 16).json()

    response = client.patch(f"{BLOCKS}/{block['id']}", json={"end_date": day(20).isoformat()})

    assert response.status_code == 409


def test_empty_block_update_returns_400(client: TestClient, create_block: Api) -> None:
    block = create_block(11, 16).json()

    assert client.patch(f"{BLOCKS}/{block['id']}", json={}).status_code == 400


def test_update_missing_block_returns_404(client: TestClient) -> None:
    response = client.patch(f"{BLOCKS}/999", json={"end_date": day(20).isoformat()})

    assert response.status_code == 404


def test_delete_block_frees_dates(
    client: TestClient, create_block: Api, create_booking: Api
) -> None:
    block = create_block(11, 16).json()

    assert client.delete(f"{BLOCKS}/{block['id']}").status_code == 204
    assert client.get(f"{BLOCKS}/{block['id']}").status_code == 404
    assert client.delete(f"{BLOCKS}/{block['id']}").status_code == 404
    assert create_booking(11, 16).status_code == 201
