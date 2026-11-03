from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.errors import ERROR_RESPONSES
from app.api.routes import blocks, bookings, properties

api_router = APIRouter(
    prefix="/api/v1", dependencies=[Depends(require_api_key)], responses=ERROR_RESPONSES
)
api_router.include_router(properties.router)
api_router.include_router(bookings.router)
api_router.include_router(blocks.router)
