from sqlalchemy import case, exists, or_, select
from sqlalchemy.orm import Session

from equipment_lending.model.booking import Booking
from equipment_lending.model.equipment import Equipment


class EquipmentDao:
    def __init__(self, session: Session):
        self.session = session

    def find_all(self, search="", category="", status="", start_date=None, end_date=None):
        active_booking = exists().where(
            Booking.equipment_id == Equipment.id,
            Booking.status.in_(("pending", "approved", "borrowed")),
        )
        displayed_status = case(
            (active_booking, "unavailable"),
            else_=Equipment.status,
        ).label("status")
        query = select(
            Equipment.id,
            Equipment.name,
            Equipment.description,
            Equipment.category,
            Equipment.location,
            displayed_status,
        )
        if search:
            query = query.where(or_(
                Equipment.name.icontains(search, autoescape=True),
                Equipment.description.icontains(search, autoescape=True),
            ))
        if category:
            query = query.where(Equipment.category == category)
        if status:
            query = query.where(displayed_status == status)
        if start_date is not None and end_date is not None:
            query = query.where(
                Equipment.status == "available",
                ~active_booking,
            )
        return self.session.execute(
            query.order_by(Equipment.category, Equipment.name, Equipment.id)
        ).mappings().all()

    def find_categories(self):
        return self.session.scalars(select(Equipment.category).distinct().order_by(Equipment.category)).all()

    def find_by_id(self, equipment_id: int):
        return self.session.get(Equipment, equipment_id)

    def create(self, name: str, category: str, location: str, status: str, description: str):
        equipment = Equipment(name=name, category=category, location=location, status=status, description=description)
        self.session.add(equipment)
        self.session.flush()
        return equipment

    def update(self, equipment: Equipment, name: str, category: str, location: str,
               status: str, description: str):
        equipment.name = name
        equipment.category = category
        equipment.location = location
        equipment.status = status
        equipment.description = description
        self.session.flush()
        return equipment
