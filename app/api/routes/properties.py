from fastapi import APIRouter, Request, Response, status

from app.api.deps import PathId, PropertyServiceDep
from app.models import Property
from app.schemas import PropertyCreate, PropertyRead

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PropertyRead)
def create_property(
    payload: PropertyCreate, service: PropertyServiceDep, request: Request, response: Response
) -> Property:
    prop = service.create(payload)
    response.headers["Location"] = str(request.url_for("get_property", property_id=prop.id))
    return prop


@router.get("/{property_id}", response_model=PropertyRead, name="get_property")
def get_property(property_id: PathId, service: PropertyServiceDep) -> Property:
    return service.get(property_id)
