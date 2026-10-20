"""Apply booking approval and handover upgrades without replacing existing rows."""
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
            columns = {column["name"] for column in inspector.get_columns("bookings")}
            if "picked_up_at" not in columns:
                connection.exec_driver_sql("ALTER TABLE bookings ADD COLUMN picked_up_at DATETIME")
            if "returned_at" not in columns:
                connection.exec_driver_sql("ALTER TABLE bookings ADD COLUMN returned_at DATETIME")
            connection.commit()
        except Exception:
            connection.rollback()
            raise


if __name__ == "__main__":
    migrate_db()
    print("Booking approval and handover database upgrades are ready.")
