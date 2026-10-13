from equipment_lending.database import Base, engine
from equipment_lending.model.login_session import LoginSession
from equipment_lending.model.user import User


def init_db():
    """Create authentication tables without replacing existing data."""
    Base.metadata.create_all(engine, tables=[User.__table__, LoginSession.__table__])


if __name__ == "__main__":
    init_db()
    print("Authentication tables are ready.")
