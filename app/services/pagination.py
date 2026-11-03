from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


def paginate(
    session: Session,
    model: type[ModelT],
    *,
    where: Sequence[ColumnElement[bool]] = (),
    order_by: Sequence[InstrumentedAttribute[object]],
    limit: int,
    offset: int,
) -> tuple[Sequence[ModelT], int]:
    """Return one page of ``model`` rows matching ``where``, plus the total match count.

    The statement is built here from the model class (rather than accepted as a ``Select``)
    so the result stays precisely typed across SQLAlchemy 2.0 and 2.1, whose ``Select``
    generics differ.
    """
    total = session.scalar(select(func.count()).select_from(model).where(*where))
    items = session.scalars(
        select(model).where(*where).order_by(*order_by).limit(limit).offset(offset)
    ).all()
    return items, total or 0
