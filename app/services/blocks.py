from collections.abc import Sequence

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Session

from app.database import write_transaction
from app.domain import DateRange
from app.models import Block, Property
from app.schemas import BlockCreate, BlockUpdate
from app.services.availability import ensure_block_dates_available, lock_property
from app.services.lookup import get_or_404
from app.services.pagination import paginate


class BlockService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_page(
        self, *, property_id: int | None = None, limit: int, offset: int
    ) -> tuple[Sequence[Block], int]:
        where: list[ColumnElement[bool]] = []
        if property_id is not None:
            get_or_404(self._session, Property, property_id)
            where.append(Block.property_id == property_id)
        return paginate(
            self._session,
            Block,
            where=where,
            order_by=(Block.start_date, Block.id),
            limit=limit,
            offset=offset,
        )

    def get(self, block_id: int) -> Block:
        return get_or_404(self._session, Block, block_id)

    def create(self, data: BlockCreate) -> Block:
        date_range = DateRange(data.start_date, data.end_date)
        with write_transaction(self._session):
            lock_property(self._session, data.property_id)
            ensure_block_dates_available(self._session, data.property_id, date_range)
            block = Block(**data.model_dump())
            self._session.add(block)
        return block

    def update(self, block_id: int, data: BlockUpdate) -> Block:
        changes = data.model_dump(exclude_unset=True)
        with write_transaction(self._session):
            block = get_or_404(self._session, Block, block_id, for_update=True)
            new_range = DateRange(
                changes.get("start_date", block.start_date),
                changes.get("end_date", block.end_date),
            )
            if new_range != block.date_range:
                lock_property(self._session, block.property_id)
                ensure_block_dates_available(self._session, block.property_id, new_range)
            for field, value in changes.items():
                setattr(block, field, value)
        return block

    def delete(self, block_id: int) -> None:
        with write_transaction(self._session):
            block = get_or_404(self._session, Block, block_id, for_update=True)
            self._session.delete(block)
