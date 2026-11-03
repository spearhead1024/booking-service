import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Path, Query, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.exceptions import AuthenticationError
from app.schemas import MAX_DB_INT
from app.services.blocks import BlockService
from app.services.bookings import BookingService
from app.services.properties import PropertyService

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    request: Request, api_key: Annotated[str | None, Security(_api_key_header)]
) -> None:
    expected = request.app.state.settings.api_key
    if expected is None:
        return
    # Constant-time comparison avoids leaking the key through response timing.
    if api_key is None or not secrets.compare_digest(
        api_key.encode(), expected.get_secret_value().encode()
    ):
        raise AuthenticationError("Missing or invalid API key.")


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_property_service(session: SessionDep) -> PropertyService:
    return PropertyService(session)


def get_booking_service(session: SessionDep) -> BookingService:
    return BookingService(session)


def get_block_service(session: SessionDep) -> BlockService:
    return BlockService(session)


PropertyServiceDep = Annotated[PropertyService, Depends(get_property_service)]
BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]
BlockServiceDep = Annotated[BlockService, Depends(get_block_service)]

LimitQuery = Annotated[int, Query(ge=1, le=100, description="Maximum number of items.")]
OffsetQuery = Annotated[int, Query(ge=0, le=MAX_DB_INT, description="Number of items to skip.")]
PathId = Annotated[int, Path(gt=0, le=MAX_DB_INT)]
PropertyFilter = Annotated[
    int | None, Query(gt=0, le=MAX_DB_INT, description="Only items of this property.")
]
