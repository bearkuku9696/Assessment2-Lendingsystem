from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from equipment_lending.database import Base


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (CheckConstraint("status IN ('available', 'maintenance', 'inactive')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="available")
