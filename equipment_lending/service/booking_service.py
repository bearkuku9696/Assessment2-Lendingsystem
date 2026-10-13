from datetime import date

from ..dao import BookingDao, EquipmentDao
from .exceptions import AccessDeniedError, ValidationError


class BookingService:
    ALLOWED_TRANSITIONS = {
        "pending": {"approved", "rejected", "cancelled"},
        "approved": {"borrowed", "cancelled"},
        "borrowed": {"returned"},
        "rejected": set(),
        "cancelled": set(),
        "returned": set(),
    }

    def __init__(self, booking_dao=None, equipment_dao=None):
        self.booking_dao = booking_dao or BookingDao()
        self.equipment_dao = equipment_dao or EquipmentDao()

    def find_for_user(self, user_id):
        return self.booking_dao.find_by_user_id(user_id)

    def find_all(self):
        return self.booking_dao.find_all()

    def create_booking(self, user_id, equipment_id, start_date, end_date, purpose):
        equipment = self.equipment_dao.find_by_id(equipment_id)
        if equipment is None:
            raise ValidationError("Equipment was not found.")
        if equipment["status"] != "available":
            raise ValidationError(
                "This equipment is not currently available for booking."
            )

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as error:
            raise ValidationError("Enter valid start and end dates.") from error

        if start < date.today():
            raise ValidationError("The start date cannot be in the past.")
        if end <= start:
            raise ValidationError("The end date must be after the start date.")
        if not purpose.strip():
            raise ValidationError("Please explain the purpose of this booking.")
        if self.booking_dao.has_conflict(equipment_id, start_date, end_date):
            raise ValidationError(
                "The equipment is already booked for part of this period."
            )

        return self.booking_dao.create(
            user_id, equipment_id, start_date, end_date, purpose.strip()
        )

    def cancel_booking(self, booking_id, user_id):
        booking = self._find_required(booking_id)
        if booking["user_id"] != user_id:
            raise AccessDeniedError("You cannot cancel another member's booking.")
        self._change_status(booking, "cancelled")

    def change_status(self, booking_id, new_status, admin_note=""):
        booking = self._find_required(booking_id)
        self._change_status(booking, new_status, admin_note.strip())

    def _find_required(self, booking_id):
        booking = self.booking_dao.find_by_id(booking_id)
        if booking is None:
            raise ValidationError("Booking was not found.")
        return booking

    def _change_status(self, booking, new_status, admin_note=""):
        if new_status not in self.ALLOWED_TRANSITIONS[booking["status"]]:
            raise ValidationError(
                f"A {booking['status']} booking cannot be changed to {new_status}."
            )
        if new_status == "approved":
            if not self.booking_dao.approve_if_available(booking, admin_note):
                raise ValidationError("Another approved booking overlaps this period.")
            return
        self.booking_dao.update_status(booking["id"], new_status, admin_note)
