from sqlalchemy import inspect

from equipment_lending.database import Base, engine
from equipment_lending.model.login_session import LoginSession
from equipment_lending.model.user import User
from equipment_lending.model.equipment import Equipment
from equipment_lending.model.booking import Booking


def init_db():
    """Create application tables without replacing existing data."""
    Base.metadata.create_all(engine, tables=[User.__table__, LoginSession.__table__, Equipment.__table__, Booking.__table__])
    with engine.begin() as connection:
        booking_columns = {column["name"] for column in inspect(connection).get_columns("bookings")}
        if "admin_notes" not in booking_columns:
            connection.exec_driver_sql(
                "ALTER TABLE bookings ADD COLUMN admin_notes VARCHAR(2000) NOT NULL DEFAULT ''"
            )


if __name__ == "__main__":
    init_db()
    print("Application tables are ready.")
