"""SQLAlchemy ORM models.

Integrity rules are duplicated as database constraints (date order, status values, foreign
keys) so that data written outside the API cannot violate them either.
"""

from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain import BookingStatus, DateRange


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2))


class _PropertyDateRange:
    """Columns shared by everything that occupies days on a property."""

    # RESTRICT: deleting a property must never silently erase its booking history.
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    @property
    def date_range(self) -> DateRange:
        return DateRange(self.start_date, self.end_date)


class Booking(_PropertyDateRange, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("start_date < end_date", name="ck_bookings_date_order"),
        # Serves the overlap query: equality on property, range scan on dates.
        Index("ix_bookings_availability", "property_id", "start_date", "end_date", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    guest_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, native_enum=False, create_constraint=True, length=16),
        default=BookingStatus.CONFIRMED,
    )

    @property
    def occupies_dates(self) -> bool:
        return self.status is not BookingStatus.CANCELED


class Block(_PropertyDateRange, Base):
    __tablename__ = "blocks"
    __table_args__ = (
        CheckConstraint("start_date < end_date", name="ck_blocks_date_order"),
        Index("ix_blocks_availability", "property_id", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
