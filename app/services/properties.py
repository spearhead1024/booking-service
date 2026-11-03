from sqlalchemy.orm import Session

from app.database import write_transaction
from app.models import Property
from app.schemas import PropertyCreate
from app.services.lookup import get_or_404


class PropertyService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, property_id: int) -> Property:
        return get_or_404(self._session, Property, property_id)

    def create(self, data: PropertyCreate) -> Property:
        prop = Property(**data.model_dump())
        with write_transaction(self._session):
            self._session.add(prop)
        return prop
