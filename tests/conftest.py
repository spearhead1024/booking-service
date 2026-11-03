from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.overlap_cases import day

Api = Callable[..., httpx.Response]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}", api_key=None)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def property_id(client: TestClient) -> int:
    response = client.post("/api/v1/properties", json={"name": "Beach House", "country_code": "PT"})
    assert response.status_code == 201
    return int(response.json()["id"])


@pytest.fixture
def create_booking(client: TestClient, property_id: int) -> Api:
    def _create(start: int, end: int, **overrides: Any) -> httpx.Response:
        payload = {
            "property_id": property_id,
            "guest_name": "Jane Doe",
            "start_date": day(start).isoformat(),
            "end_date": day(end).isoformat(),
            **overrides,
        }
        return client.post("/api/v1/bookings", json=payload)

    return _create


@pytest.fixture
def create_block(client: TestClient, property_id: int) -> Api:
    def _create(start: int, end: int, **overrides: Any) -> httpx.Response:
        payload = {
            "property_id": property_id,
            "start_date": day(start).isoformat(),
            "end_date": day(end).isoformat(),
            **overrides,
        }
        return client.post("/api/v1/blocks", json=payload)

    return _create
