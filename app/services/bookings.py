from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import write_transaction
from app.domain import BookingStatus, DateRange
from app.exceptions import InvalidStateTransitionError
from app.models import Booking, Property
from app.schemas import BookingCreate, BookingUpdate
from app.services.availability import ensure_booking_dates_available, lock_property
from app.services.lookup import get_or_404
from app.services.pagination import paginate


class BookingService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_page(
        self,
        *,
        property_id: int | None = None,
        status: BookingStatus | None = None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Booking], int]:
        stmt = select(Booking).order_by(Booking.start_date, Booking.id)
        if property_id is not None:
            get_or_404(self._session, Property, property_id)
            stmt = stmt.where(Booking.property_id == property_id)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        return paginate(self._session, stmt, limit=limit, offset=offset)

    def get(self, booking_id: int) -> Booking:
        return get_or_404(self._session, Booking, booking_id)

    def create(self, data: BookingCreate) -> Booking:
        date_range = DateRange(data.start_date, data.end_date)
        with write_transaction(self._session):
            lock_property(self._session, data.property_id)
            ensure_booking_dates_available(self._session, data.property_id, date_range)
            booking = Booking(**data.model_dump(), status=BookingStatus.CONFIRMED)
            self._session.add(booking)
        return booking

    def update(self, booking_id: int, data: BookingUpdate) -> Booking:
        changes = data.model_dump(exclude_unset=True)
        with write_transaction(self._session):
            booking = get_or_404(self._session, Booking, booking_id, for_update=True)
            new_range = DateRange(
                changes.get("start_date", booking.start_date),
                changes.get("end_date", booking.end_date),
            )
            # A canceled booking holds no dates; it is re-checked on rebook instead.
            if booking.occupies_dates and new_range != booking.date_range:
                lock_property(self._session, booking.property_id)
                ensure_booking_dates_available(
                    self._session, booking.property_id, new_range, exclude_booking_id=booking.id
                )
            for field, value in changes.items():
                setattr(booking, field, value)
        return booking

    def cancel(self, booking_id: int) -> Booking:
        with write_transaction(self._session):
            booking = get_or_404(self._session, Booking, booking_id, for_update=True)
            if booking.status is BookingStatus.CANCELED:
                raise InvalidStateTransitionError(f"Booking {booking_id} is already canceled.")
            booking.status = BookingStatus.CANCELED
        return booking

    def rebook(self, booking_id: int) -> Booking:
        with write_transaction(self._session):
            booking = get_or_404(self._session, Booking, booking_id, for_update=True)
            if booking.status is not BookingStatus.CANCELED:
                raise InvalidStateTransitionError(
                    f"Booking {booking_id} is not canceled; only canceled bookings can be rebooked."
                )
            lock_property(self._session, booking.property_id)
            ensure_booking_dates_available(
                self._session,
                booking.property_id,
                booking.date_range,
                exclude_booking_id=booking.id,
            )
            booking.status = BookingStatus.CONFIRMED
        return booking

    def delete(self, booking_id: int) -> None:
        with write_transaction(self._session):
            booking = get_or_404(self._session, Booking, booking_id, for_update=True)
            self._session.delete(booking)
