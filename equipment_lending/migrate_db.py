"""Apply the booking approval upgrade to an initialized SQLite database."""
from sqlalchemy import inspect

from equipment_lending.database import engine


def migrate_db():
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            inspector = inspect(connection)
            if not inspector.has_table("bookings"):
                raise RuntimeError("Initialize the database with python -m equipment_lending.init_db first.")
            if "admin_notes" not in {column["name"] for column in inspector.get_columns("bookings")}:
                connection.exec_driver_sql(
                    "ALTER TABLE bookings ADD COLUMN admin_notes VARCHAR(2000) NOT NULL DEFAULT ''"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


if __name__ == "__main__":
    migrate_db()
    print("Booking approval database upgrade is ready.")
