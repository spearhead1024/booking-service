"""Availability rules shared by bookings and blocks.

Invariant: no non-canceled booking shares a day with another non-canceled booking or with a
block on the same property. Callers must run these checks inside ``write_transaction`` after
``lock_property`` so the check and the subsequent write are atomic.
"""

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.domain import BookingStatus, DateRange
from app.exceptions import DateOverlapError
from app.models import Block, Booking, Property
from app.services.lookup import get_or_404


def lock_property(session: Session, property_id: int) -> Property:
    """Load the property, taking a row lock where the backend supports it."""
    return get_or_404(session, Property, property_id, for_update=True)


def ensure_booking_dates_available(
    session: Session,
    property_id: int,
    date_range: DateRange,
    *,
    exclude_booking_id: int | None = None,
) -> None:
    """Raise if ``date_range`` collides with a block or another non-canceled booking."""
    block = _first_overlapping_block(session, property_id, date_range)
    if block is not None:
        raise _overlap_error("block", block.id, block.date_range)

    booking = _first_overlapping_booking(session, property_id, date_range, exclude_booking_id)
    if booking is not None:
        raise _overlap_error("booking", booking.id, booking.date_range)


def ensure_block_dates_available(session: Session, property_id: int, date_range: DateRange) -> None:
    """Raise if a block over ``date_range`` would cover an existing non-canceled booking."""
    booking = _first_overlapping_booking(session, property_id, date_range, exclude_id=None)
    if booking is not None:
        raise _overlap_error("booking", booking.id, booking.date_range)


def _overlaps(
    start_column: InstrumentedAttribute[object],
    end_column: InstrumentedAttribute[object],
    date_range: DateRange,
) -> ColumnElement[bool]:
    # SQL form of DateRange.overlaps: closed intervals intersect iff each starts no later
    # than the other ends.
    return and_(start_column <= date_range.end, end_column >= date_range.start)


def _first_overlapping_block(
    session: Session, property_id: int, date_range: DateRange
) -> Block | None:
    stmt = (
        select(Block)
        .where(
            Block.property_id == property_id,
            _overlaps(Block.start_date, Block.end_date, date_range),
        )
        .order_by(Block.start_date)
        .limit(1)
    )
    return session.scalar(stmt)


def _first_overlapping_booking(
    session: Session, property_id: int, date_range: DateRange, exclude_id: int | None
) -> Booking | None:
    stmt = (
        select(Booking)
        .where(
            Booking.property_id == property_id,
            Booking.status != BookingStatus.CANCELED,
            _overlaps(Booking.start_date, Booking.end_date, date_range),
        )
        .order_by(Booking.start_date)
        .limit(1)
    )
    if exclude_id is not None:
        stmt = stmt.where(Booking.id != exclude_id)
    return session.scalar(stmt)


def _overlap_error(kind: str, conflict_id: int, conflict_range: DateRange) -> DateOverlapError:
    return DateOverlapError(
        f"The requested dates overlap an existing {kind}.",
        details={
            "conflict_type": kind,
            "conflict_id": conflict_id,
            "start_date": conflict_range.start.isoformat(),
            "end_date": conflict_range.end.isoformat(),
        },
    )
