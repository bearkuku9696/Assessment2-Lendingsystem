from ..dao import EquipmentDao


class EquipmentService:
    def __init__(self, equipment_dao=None):
        self.equipment_dao = equipment_dao or EquipmentDao()

    def find_all(self, search="", category="", status=""):
        return self.equipment_dao.find_all(search, category, status)

    def find_categories(self):
        return self.equipment_dao.find_categories()

    def find_by_id(self, equipment_id):
        return self.equipment_dao.find_by_id(equipment_id)

    def create(self, name, category, description, location, status):
        return self.equipment_dao.create(
            name, category, description, location, status
        )

    def update(self, equipment_id, name, category, description, location, status):
        self.equipment_dao.update(
            equipment_id, name, category, description, location, status
        )
