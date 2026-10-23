from sqlalchemy.orm import Session

from equipment_lending.dao.equipment_dao import EquipmentDao


class EquipmentNotFound(Exception):
    pass


class EquipmentService:
    def __init__(self, session: Session):
        self.session = session
        self.equipment = EquipmentDao(session)

    def find_all(self, search="", category="", status="", start_date=None, end_date=None):
        return self.equipment.find_all(search.strip(), category, status, start_date, end_date)

    def find_categories(self):
        return self.equipment.find_categories()

    def create(self, name: str, category: str, location: str, status: str, description: str):
        with self.session.begin():
            equipment = self.equipment.create(name, category, location, status, description)
        return equipment

    def update(self, equipment_id: int, name: str, category: str, location: str,
               status: str, description: str):
        with self.session.begin():
            equipment = self.equipment.find_by_id(equipment_id)
            if equipment is None:
                raise EquipmentNotFound
            self.equipment.update(equipment, name, category, location, status, description)
        return equipment
