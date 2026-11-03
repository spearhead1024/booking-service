from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


def paginate(
    session: Session, stmt: Select[T], *, limit: int, offset: int
) -> tuple[Sequence[T], int]:
    """Return one page of single-entity ``stmt`` plus the total number of matching rows."""
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = session.scalars(stmt.limit(limit).offset(offset)).all()
    return items, total or 0
