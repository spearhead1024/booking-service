from fastapi import APIRouter, Request, Response, status

from app.api.deps import BlockServiceDep, LimitQuery, OffsetQuery, PathId, PropertyFilter
from app.models import Block
from app.schemas import BlockCreate, BlockRead, BlockUpdate, Page

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.get("", response_model=Page[BlockRead])
def list_blocks(
    service: BlockServiceDep,
    property_id: PropertyFilter = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Page[BlockRead]:
    items, total = service.list_page(property_id=property_id, limit=limit, offset=offset)
    return Page(
        items=[BlockRead.model_validate(b) for b in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BlockRead)
def create_block(
    payload: BlockCreate, service: BlockServiceDep, request: Request, response: Response
) -> Block:
    """Block a date range. Rejected if it would cover an existing confirmed booking."""
    block = service.create(payload)
    response.headers["Location"] = str(request.url_for("get_block", block_id=block.id))
    return block


@router.get("/{block_id}", response_model=BlockRead, name="get_block")
def get_block(block_id: PathId, service: BlockServiceDep) -> Block:
    return service.get(block_id)


@router.patch("/{block_id}", response_model=BlockRead)
def update_block(block_id: PathId, payload: BlockUpdate, service: BlockServiceDep) -> Block:
    return service.update(block_id, payload)


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(block_id: PathId, service: BlockServiceDep) -> None:
    service.delete(block_id)
