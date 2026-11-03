from typing import TypeVar

from sqlalchemy.orm import Session

from app.database import Base
from app.exceptions import NotFoundError

ModelT = TypeVar("ModelT", bound=Base)


def get_or_404(
    session: Session, model: type[ModelT], entity_id: int, *, for_update: bool = False
) -> ModelT:
    """Load an entity by primary key or raise ``NotFoundError``.

    ``for_update`` takes a row lock on backends that support ``SELECT ... FOR UPDATE``.
    """
    entity = session.get(model, entity_id, with_for_update=for_update or None)
    if entity is None:
        raise NotFoundError(model.__name__, entity_id)
    return entity
