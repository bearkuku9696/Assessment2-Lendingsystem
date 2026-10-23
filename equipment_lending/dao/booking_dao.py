from sqlalchemy import select, update
from sqlalchemy.orm import Session

from equipment_lending.model.booking import Booking
from equipment_lending.model.equipment import Equipment
from equipment_lending.model.user import User


class BookingDao:
    def __init__(self, session: Session):
        self.session = session

    def find_by_user_id(self, user_id: int):
        return self.session.scalars(select(Booking).where(Booking.user_id == user_id).order_by(Booking.id.desc())).all()

    def find_all(self):
        return self.session.execute(self.admin_query().order_by(Booking.id.desc())).mappings().all()

    @staticmethod
    def admin_query():
        return select(
            *Booking.__table__.c,
            User.name.label("applicant_name"),
            User.email.label("applicant_email"),
            Equipment.name.label("equipment_name"),
        ).join(User, User.id == Booking.user_id).join(Equipment, Equipment.id == Booking.equipment_id)

    def find_for_admin(self, booking_id: int):
        return self.session.execute(self.admin_query().where(Booking.id == booking_id)).mappings().one()

    def review(self, booking: Booking, status: str, admin_notes: str):
        booking.status = status
        booking.admin_notes = admin_notes
        self.session.flush()

    def record_pickup(self, booking: Booking, picked_up_at):
        booking.status = "borrowed"
        booking.picked_up_at = picked_up_at
        self.session.flush()

    def record_return(self, booking: Booking, returned_at):
        booking.status = "returned"
        booking.returned_at = returned_at
        self.session.flush()

    def find_by_id(self, booking_id: int):
        return self.session.get(Booking, booking_id)

    def has_conflict(self, equipment_id: int, start_date, end_date) -> bool:
        return self.session.scalar(
            select(Booking.id).where(
                Booking.equipment_id == equipment_id,
                Booking.status.in_(("approved", "borrowed")),
                Booking.start_date <= end_date,
                Booking.end_date >= start_date,
            ).limit(1)
        ) is not None

    def has_active_booking(self, equipment_id: int) -> bool:
        return self.session.scalar(
            select(Booking.id).where(
                Booking.equipment_id == equipment_id,
                Booking.status.in_(("pending", "approved", "borrowed")),
            ).limit(1)
        ) is not None

    def create(self, user_id: int, equipment_id: int, start_date, end_date, purpose: str):
        booking = Booking(user_id=user_id, equipment_id=equipment_id, start_date=start_date,
                          end_date=end_date, purpose=purpose, status="pending")
        self.session.add(booking)
        self.session.flush()
        return booking

    def cancel(self, booking_id: int, user_id: int) -> bool:
        result = self.session.execute(
            update(Booking).where(Booking.id == booking_id, Booking.user_id == user_id,
                                  Booking.status.in_(("pending", "approved"))).values(status="cancelled")
        )
        return result.rowcount == 1
