from sqlalchemy import select
from sqlalchemy.orm import Session

from equipment_lending.model.equipment import Equipment


class EquipmentDao:
    def __init__(self, session: Session):
        self.session = session

    def find_all(self):
        return self.session.scalars(select(Equipment).order_by(Equipment.category, Equipment.name, Equipment.id)).all()

    def find_by_id(self, equipment_id: int):
        return self.session.get(Equipment, equipment_id)

    def create(self, name: str, category: str, location: str, status: str):
        equipment = Equipment(name=name, category=category, location=location, status=status)
        self.session.add(equipment)
        self.session.flush()
        return equipment
