from ..db import get_db


class BookingDao:
    OVERDUE_SQL = """
        CASE
            WHEN bookings.status = 'borrowed'
             AND bookings.end_date < date('now') THEN 1
            ELSE 0
        END AS is_overdue
    """

    def find_by_user_id(self, user_id):
        return get_db().execute(
            f"""
            SELECT bookings.*, equipment.name AS equipment_name,
                   equipment.category AS equipment_category,
                   {self.OVERDUE_SQL}
            FROM bookings
            JOIN equipment ON equipment.id = bookings.equipment_id
            WHERE bookings.user_id = ?
            ORDER BY bookings.created_at DESC
            """,
            (user_id,),
        ).fetchall()

    def find_all(self):
        return get_db().execute(
            f"""
            SELECT bookings.*, equipment.name AS equipment_name,
                   users.name AS user_name, users.email AS user_email,
                   {self.OVERDUE_SQL}
            FROM bookings
            JOIN equipment ON equipment.id = bookings.equipment_id
            JOIN users ON users.id = bookings.user_id
            ORDER BY
                CASE bookings.status WHEN 'pending' THEN 0 ELSE 1 END,
                bookings.created_at DESC
            """
        ).fetchall()

    def find_by_id(self, booking_id):
        return get_db().execute(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()

    def has_conflict(self, equipment_id, start_date, end_date):
        return get_db().execute(
            """
            SELECT 1 FROM bookings
            WHERE equipment_id = ?
              AND status IN ('approved', 'borrowed')
              AND start_date <= ?
              AND end_date >= ?
            """,
            (equipment_id, end_date, start_date),
        ).fetchone() is not None

    def create(self, user_id, equipment_id, start_date, end_date, purpose):
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO bookings (user_id, equipment_id, start_date, end_date, purpose)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, equipment_id, start_date, end_date, purpose),
        )
        db.commit()
        return cursor.lastrowid

    def update_status(self, booking_id, status, admin_note=""):
        timestamp_column = {
            "borrowed": "collected_at",
            "returned": "returned_at",
        }.get(status)
        timestamp_update = (
            f", {timestamp_column} = CURRENT_TIMESTAMP" if timestamp_column else ""
        )

        db = get_db()
        db.execute(
            f"""
            UPDATE bookings
            SET status = ?, admin_note = ?{timestamp_update}
            WHERE id = ?
            """,
            (status, admin_note, booking_id),
        )
        db.commit()

    def approve_if_available(self, booking, admin_note=""):
        db = get_db()
        db.execute("BEGIN IMMEDIATE")
        conflict = db.execute(
            """
            SELECT 1 FROM bookings
            WHERE equipment_id = ?
              AND status IN ('approved', 'borrowed')
              AND start_date <= ?
              AND end_date >= ?
              AND id != ?
            """,
            (
                booking["equipment_id"],
                booking["end_date"],
                booking["start_date"],
                booking["id"],
            ),
        ).fetchone()
        if conflict:
            db.rollback()
            return False

        db.execute(
            "UPDATE bookings SET status = 'approved', admin_note = ? WHERE id = ?",
            (admin_note, booking["id"]),
        )
        db.commit()
        return True
