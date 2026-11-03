"""Framework-independent domain types and rules."""

import enum
from dataclasses import dataclass
from datetime import date

from app.exceptions import InvalidDateRangeError

DATE_ORDER_MESSAGE = "start_date must be before end_date"


class BookingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


@dataclass(frozen=True, slots=True)
class DateRange:
    """A range of days where both ``start`` and ``end`` are occupied (closed interval)."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise InvalidDateRangeError(DATE_ORDER_MESSAGE)

    def overlaps(self, other: "DateRange") -> bool:
        """Return True if the ranges share at least one day (boundaries are inclusive)."""
        return self.start <= other.end and other.start <= self.end
