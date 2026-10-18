from sqlalchemy.orm import Session

from equipment_lending.dao.equipment_dao import EquipmentDao


class EquipmentService:
    def __init__(self, session: Session):
        self.session = session
        self.equipment = EquipmentDao(session)

    def find_all(self):
        return self.equipment.find_all()

    def create(self, name: str, category: str, location: str, status: str):
        with self.session.begin():
            equipment = self.equipment.create(name, category, location, status)
        return equipment
