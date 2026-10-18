from sqlalchemy.orm import Session

from equipment_lending.dao.booking_dao import BookingDao
from equipment_lending.dao.equipment_dao import EquipmentDao
from equipment_lending.schema.booking import BookingRequest


class BookingNotFound(Exception):
    pass


class EquipmentNotFound(Exception):
    pass


class EquipmentUnavailable(Exception):
    pass


class BookingDateConflict(Exception):
    pass


class AccessDeniedError(Exception):
    pass


class BookingCannotBeCancelled(Exception):
    pass


class BookingService:
    def __init__(self, session: Session):
        self.session = session
        self.bookings = BookingDao(session)
        self.equipment = EquipmentDao(session)

    def find_for_user(self, user_id: int):
        return self.bookings.find_by_user_id(user_id)

    def find_all(self):
        return self.bookings.find_all()

    def get_available_equipment(self, equipment_id: int):
        equipment = self.equipment.find_by_id(equipment_id)
        if equipment is None:
            raise EquipmentNotFound
        if equipment.status != "available":
            raise EquipmentUnavailable
        return equipment

    def find_for_owner(self, booking_id: int, user_id: int):
        booking = self.bookings.find_by_id(booking_id)
        if booking is None:
            raise BookingNotFound
        if booking.user_id != user_id:
            raise AccessDeniedError
        return booking

    def create_booking(self, user_id: int, data: BookingRequest):
        with self.session.begin():
            self.get_available_equipment(data.equipment_id)
            if self.bookings.has_conflict(data.equipment_id, data.start_date, data.end_date):
                raise BookingDateConflict
            booking = self.bookings.create(user_id, data.equipment_id, data.start_date, data.end_date, data.purpose)
        return booking

    def cancel_booking(self, booking_id: int, user_id: int):
        with self.session.begin():
            booking = self.find_for_owner(booking_id, user_id)
            if not self.bookings.cancel(booking_id, user_id):
                raise BookingCannotBeCancelled
        return booking
