import pytest
from pydantic import ValidationError

from app.schemas import BookingCreate, BookingUpdate, PropertyCreate


def test_property_normalizes_name_and_country_code() -> None:
    prop = PropertyCreate(name="  Villa  ", country_code=" pt ")

    assert (prop.name, prop.country_code) == ("Villa", "PT")


@pytest.mark.parametrize("country_code", ["P", "PRT", "P1", ""])
def test_property_rejects_invalid_country_code(country_code: str) -> None:
    with pytest.raises(ValidationError):
        PropertyCreate(name="Villa", country_code=country_code)


def test_booking_rejects_blank_guest_name() -> None:
    with pytest.raises(ValidationError):
        BookingCreate(
            property_id=1, guest_name="   ", start_date="2030-01-01", end_date="2030-01-02"
        )


def test_booking_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(
            {
                "property_id": 1,
                "guest_name": "Jane",
                "start_date": "2030-01-01",
                "end_date": "2030-01-02",
                "status": "CANCELED",
            }
        )


def test_update_tracks_only_supplied_fields() -> None:
    update = BookingUpdate.model_validate({"guest_name": "John"})

    assert update.model_dump(exclude_unset=True) == {"guest_name": "John"}


def test_update_rejects_explicit_null() -> None:
    with pytest.raises(ValidationError, match="cannot be null"):
        BookingUpdate.model_validate({"start_date": None})


def test_update_rejects_reversed_dates_when_both_given() -> None:
    with pytest.raises(ValidationError, match="start_date must be before end_date"):
        BookingUpdate.model_validate({"start_date": "2030-01-05", "end_date": "2030-01-01"})
