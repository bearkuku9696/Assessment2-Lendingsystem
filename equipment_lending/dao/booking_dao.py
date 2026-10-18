from sqlalchemy import select, update
from sqlalchemy.orm import Session

from equipment_lending.model.booking import Booking


class BookingDao:
    def __init__(self, session: Session):
        self.session = session

    def find_by_user_id(self, user_id: int):
        return self.session.scalars(select(Booking).where(Booking.user_id == user_id).order_by(Booking.id.desc())).all()

    def find_all(self):
        return self.session.scalars(select(Booking).order_by(Booking.id.desc())).all()

    def find_by_id(self, booking_id: int):
        return self.session.get(Booking, booking_id)

    def create(self, user_id: int, equipment_id: int, start_date, end_date, purpose: str):
        booking = Booking(user_id=user_id, equipment_id=equipment_id, start_date=start_date,
                          end_date=end_date, purpose=purpose)
        self.session.add(booking)
        self.session.flush()
        return booking

    def cancel(self, booking_id: int, user_id: int) -> bool:
        result = self.session.execute(
            update(Booking).where(Booking.id == booking_id, Booking.user_id == user_id,
                                  Booking.status.in_(("pending", "approved"))).values(status="cancelled")
        )
        return result.rowcount == 1
