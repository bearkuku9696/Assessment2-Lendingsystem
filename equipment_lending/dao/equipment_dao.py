from ..db import get_db


class EquipmentDao:
    def find_all(self, search="", category="", status=""):
        clauses = []
        params = []
        if search:
            clauses.append(
                "(lower(name) LIKE lower(?) OR lower(description) LIKE lower(?))"
            )
            value = f"%{search}%"
            params.extend([value, value])
        if category:
            clauses.append("category = ?")
            params.append(category)
        if status:
            clauses.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return get_db().execute(
            f"SELECT * FROM equipment {where} ORDER BY category, name", params
        ).fetchall()

    def find_categories(self):
        rows = get_db().execute(
            "SELECT DISTINCT category FROM equipment ORDER BY category"
        ).fetchall()
        return [row["category"] for row in rows]

    def find_by_id(self, equipment_id):
        return get_db().execute(
            "SELECT * FROM equipment WHERE id = ?", (equipment_id,)
        ).fetchone()

    def create(self, name, category, description, location, status):
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO equipment (name, category, description, location, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, category, description, location, status),
        )
        db.commit()
        return cursor.lastrowid

    def update(self, equipment_id, name, category, description, location, status):
        db = get_db()
        db.execute(
            """
            UPDATE equipment
            SET name = ?, category = ?, description = ?, location = ?, status = ?
            WHERE id = ?
            """,
            (name, category, description, location, status, equipment_id),
        )
        db.commit()
