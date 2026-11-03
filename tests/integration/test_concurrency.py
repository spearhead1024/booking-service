"""Concurrent writers must not be able to double-book the same dates."""

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import Base, create_db_engine, create_session_factory
from app.domain import BookingStatus
from app.exceptions import DateOverlapError
from app.models import Booking
from app.schemas import BookingCreate, PropertyCreate
from app.services.availability import ensure_booking_dates_available
from app.services.bookings import BookingService
from app.services.properties import PropertyService
from tests.overlap_cases import day

WRITERS = 6


@pytest.fixture
def session_factory(settings: Settings) -> Iterator[sessionmaker[Session]]:
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


def test_simultaneous_bookings_for_same_dates_only_one_wins(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_factory() as session:
        property_id = (
            PropertyService(session).create(PropertyCreate(name="X", country_code="PT")).id
        )

    # Widen the gap between "check availability" and "insert" so that, without proper
    # locking, every writer would pass the check before any of them commits.
    def slow_check(*args: Any, **kwargs: Any) -> None:
        ensure_booking_dates_available(*args, **kwargs)
        time.sleep(0.1)

    monkeypatch.setattr("app.services.bookings.ensure_booking_dates_available", slow_check)
    barrier = threading.Barrier(WRITERS)

    def attempt(writer: int) -> str:
        barrier.wait()
        with session_factory() as session:
            try:
                BookingService(session).create(
                    BookingCreate(
                        property_id=property_id,
                        guest_name=f"Guest {writer}",
                        start_date=day(11),
                        end_date=day(16),
                    )
                )
            except DateOverlapError:
                return "conflict"
            return "created"

    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        outcomes = list(pool.map(attempt, range(WRITERS)))

    assert sorted(outcomes) == ["conflict"] * (WRITERS - 1) + ["created"]
    with session_factory() as session:
        confirmed = session.scalar(
            select(func.count()).where(Booking.status == BookingStatus.CONFIRMED)
        )
    assert confirmed == 1
