from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import BookingServiceDep, LimitQuery, OffsetQuery, PathId, PropertyFilter
from app.domain import BookingStatus
from app.models import Booking
from app.schemas import BookingCreate, BookingRead, BookingUpdate, Page

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("", response_model=Page[BookingRead])
def list_bookings(
    service: BookingServiceDep,
    property_id: PropertyFilter = None,
    booking_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Page[BookingRead]:
    items, total = service.list_page(
        property_id=property_id, status=booking_status, limit=limit, offset=offset
    )
    return Page(
        items=[BookingRead.model_validate(b) for b in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BookingRead)
def create_booking(
    payload: BookingCreate, service: BookingServiceDep, request: Request, response: Response
) -> Booking:
    booking = service.create(payload)
    response.headers["Location"] = str(request.url_for("get_booking", booking_id=booking.id))
    return booking


@router.get("/{booking_id}", response_model=BookingRead, name="get_booking")
def get_booking(booking_id: PathId, service: BookingServiceDep) -> Booking:
    return service.get(booking_id)


@router.patch("/{booking_id}", response_model=BookingRead)
def update_booking(
    booking_id: PathId, payload: BookingUpdate, service: BookingServiceDep
) -> Booking:
    """Update guest details and/or dates. Omitted fields are left unchanged."""
    return service.update(booking_id, payload)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(booking_id: PathId, service: BookingServiceDep) -> Booking:
    """Cancel a confirmed booking, releasing its dates."""
    return service.cancel(booking_id)


@router.post("/{booking_id}/rebook", response_model=BookingRead)
def rebook_booking(booking_id: PathId, service: BookingServiceDep) -> Booking:
    """Re-confirm a canceled booking, provided its dates are still available."""
    return service.rebook(booking_id)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: PathId, service: BookingServiceDep) -> None:
    service.delete(booking_id)
