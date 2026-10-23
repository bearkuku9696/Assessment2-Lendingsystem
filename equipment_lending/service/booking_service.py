from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from equipment_lending.dao.booking_dao import BookingDao
from equipment_lending.dao.equipment_dao import EquipmentDao
from equipment_lending.database import immediate_transaction
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


class BookingCannotBeReviewed(Exception):
    pass


class BookingOperationBusy(Exception):
    pass


class BookingCannotBePickedUp(Exception):
    pass


class BookingCannotBeReturned(Exception):
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
        equipment = self._get_operationally_available_equipment(equipment_id)
        if self.bookings.has_active_booking(equipment_id):
            raise EquipmentUnavailable
        return equipment

    def _get_operationally_available_equipment(self, equipment_id: int):
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
        with self._write_transaction():
            self.get_available_equipment(data.equipment_id)
            if self.bookings.has_conflict(data.equipment_id, data.start_date, data.end_date):
                raise BookingDateConflict
            booking = self.bookings.create(user_id, data.equipment_id, data.start_date, data.end_date, data.purpose)
        return booking

    def cancel_booking(self, booking_id: int, user_id: int):
        with self._write_transaction():
            booking = self.find_for_owner(booking_id, user_id)
            if not self.bookings.cancel(booking_id, user_id):
                raise BookingCannotBeCancelled
        return booking

    @contextmanager
    def _write_transaction(self):
        try:
            with immediate_transaction(self.session):
                yield
        except OperationalError as error:
            if (getattr(error.orig, "sqlite_errorcode", 0) & 0xFF) in (5, 6):
                raise BookingOperationBusy from error
            raise

    def pickup_booking(self, booking_id: int):
        with self._write_transaction():
            booking = self.bookings.find_by_id(booking_id)
            if booking is None:
                raise BookingNotFound
            if booking.status != "approved":
                raise BookingCannotBePickedUp
            self.bookings.record_pickup(booking, datetime.now(UTC).replace(tzinfo=None))
            result = self.bookings.find_for_admin(booking_id)
        return result

    def return_booking(self, booking_id: int):
        with self._write_transaction():
            booking = self.bookings.find_by_id(booking_id)
            if booking is None:
                raise BookingNotFound
            if booking.status != "borrowed":
                raise BookingCannotBeReturned
            self.bookings.record_return(booking, datetime.now(UTC).replace(tzinfo=None))
            result = self.bookings.find_for_admin(booking_id)
        return result

    def approve_booking(self, booking_id: int, admin_notes: str):
        return self._review_booking(booking_id, "approved", admin_notes)

    def reject_booking(self, booking_id: int, admin_notes: str):
        return self._review_booking(booking_id, "rejected", admin_notes)

    def _review_booking(self, booking_id: int, status: str, admin_notes: str):
        with self._write_transaction():
            booking = self.bookings.find_by_id(booking_id)
            if booking is None:
                raise BookingNotFound
            if booking.status != "pending":
                raise BookingCannotBeReviewed
            if status == "approved":
                self._get_operationally_available_equipment(booking.equipment_id)
                if self.bookings.has_conflict(booking.equipment_id, booking.start_date, booking.end_date):
                    raise BookingDateConflict
            self.bookings.review(booking, status, admin_notes)
            result = self.bookings.find_for_admin(booking_id)
        return result
