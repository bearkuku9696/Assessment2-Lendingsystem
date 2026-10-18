from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from equipment_lending.model.equipment import Equipment


class EquipmentDao:
    def __init__(self, session: Session):
        self.session = session

    def find_all(self, search="", category="", status=""):
        query = select(Equipment)
        if search:
            query = query.where(or_(
                Equipment.name.icontains(search, autoescape=True),
                Equipment.description.icontains(search, autoescape=True),
            ))
        if category:
            query = query.where(Equipment.category == category)
        if status:
            query = query.where(Equipment.status == status)
        return self.session.scalars(query.order_by(Equipment.category, Equipment.name, Equipment.id)).all()

    def find_categories(self):
        return self.session.scalars(select(Equipment.category).distinct().order_by(Equipment.category)).all()

    def find_by_id(self, equipment_id: int):
        return self.session.get(Equipment, equipment_id)

    def create(self, name: str, category: str, location: str, status: str, description: str):
        equipment = Equipment(name=name, category=category, location=location, status=status, description=description)
        self.session.add(equipment)
        self.session.flush()
        return equipment
