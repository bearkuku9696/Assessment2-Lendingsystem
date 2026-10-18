from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from equipment_lending.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
