"""Request/response schemas.

Input models are deliberately strict: unknown fields are rejected (so a typo, or an attempt
to set ``status`` directly, is a 400 rather than silently ignored), IDs must be JSON integers
and dates must be ``YYYY-MM-DD`` strings. Pydantic's default lax mode would otherwise accept
``true`` as property 1 or a Unix timestamp as a date.
"""

import re
from datetime import date, datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Strict,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from app.domain import DATE_ORDER_MESSAGE, BookingStatus

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Largest value a signed 64-bit INTEGER column holds. Bigger IDs cannot exist, and passing
# them to the driver raises OverflowError, so they are rejected as invalid input instead.
MAX_DB_INT = 2**63 - 1


def _require_iso_date(value: object) -> object:
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        return value  # Pydantic then checks it is a real calendar date.
    if isinstance(value, date) and not isinstance(value, datetime):
        return value  # Already a date (in-process callers).
    raise PydanticCustomError("date_format", "Input should be a date in YYYY-MM-DD format")


IsoDate = Annotated[date, BeforeValidator(_require_iso_date)]
EntityId = Annotated[int, Strict(), Field(gt=0, le=MAX_DB_INT)]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
CountryCode = Annotated[
    str,
    # The pattern is checked before upper-casing, hence the case-insensitive class.
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{2}$"),
    Field(description="ISO 3166-1 alpha-2 code, e.g. 'PT'. Case-insensitive on input."),
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class _DateOrderValidation(InputModel):
    """Rejects ``end_date <= start_date`` when both are in the payload.

    For partial updates the merged range (payload + stored values) is validated again by
    ``DateRange`` in the service layer.
    """

    @field_validator("end_date", check_fields=False)
    @classmethod
    def _end_after_start(cls, end: date | None, info: ValidationInfo) -> date | None:
        start = info.data.get("start_date")
        if start is not None and end is not None and start >= end:
            raise PydanticCustomError("date_order", DATE_ORDER_MESSAGE)
        return end


class _PartialUpdate(InputModel):
    """Absent fields mean "leave unchanged"; an explicit null or an empty body is rejected."""

    @model_validator(mode="after")
    def _require_non_null_fields(self) -> "_PartialUpdate":
        if not self.model_fields_set:
            raise PydanticCustomError("empty_update", "At least one field must be provided")
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise PydanticCustomError(
                "null_not_allowed", "Fields cannot be null: {fields}", {"fields": ", ".join(nulls)}
            )
        return self


# --- Properties ---------------------------------------------------------------------------


class PropertyCreate(InputModel):
    name: NonEmptyStr
    country_code: CountryCode


class PropertyRead(OutputModel):
    id: int
    name: str
    country_code: str


# --- Bookings -----------------------------------------------------------------------------


class BookingCreate(_DateOrderValidation):
    property_id: EntityId
    guest_name: NonEmptyStr
    start_date: IsoDate
    end_date: IsoDate


class BookingUpdate(_DateOrderValidation, _PartialUpdate):
    guest_name: NonEmptyStr | None = None
    start_date: IsoDate | None = None
    end_date: IsoDate | None = None


class BookingRead(OutputModel):
    id: int
    property_id: int
    guest_name: str
    start_date: date
    end_date: date
    status: BookingStatus


# --- Blocks -------------------------------------------------------------------------------


class BlockCreate(_DateOrderValidation):
    property_id: EntityId
    start_date: IsoDate
    end_date: IsoDate


class BlockUpdate(_DateOrderValidation, _PartialUpdate):
    start_date: IsoDate | None = None
    end_date: IsoDate | None = None


class BlockRead(OutputModel):
    id: int
    property_id: int
    start_date: date
    end_date: date


# --- Shared -------------------------------------------------------------------------------

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    error: str = Field(description="Stable, machine-readable error code.")
    message: str = Field(description="Human-readable description.")
    details: Any = Field(default=None, description="Optional structured context.")
