from equipment_lending.database import Base, engine
from equipment_lending.model.login_session import LoginSession
from equipment_lending.model.user import User
from equipment_lending.model.equipment import Equipment
from equipment_lending.model.booking import Booking


def init_db():
    """Create application tables without replacing existing data."""
    Base.metadata.create_all(engine, tables=[User.__table__, LoginSession.__table__, Equipment.__table__, Booking.__table__])


if __name__ == "__main__":
    init_db()
    print("Application tables are ready.")
