from sqlalchemy import select
from sqlalchemy.orm import Session

from equipment_lending.model.user import User


class UserDao:
    def __init__(self, session: Session):
        self.session = session

    def find_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def create(self, name: str, email: str, password_hash: str) -> User:
        user = User(name=name, email=email, password_hash=password_hash, role="member")
        self.session.add(user)
        self.session.flush()
        return user
