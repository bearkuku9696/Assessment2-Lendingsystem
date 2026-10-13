from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from equipment_lending.model.login_session import LoginSession
from equipment_lending.model.user import User


class LoginSessionDao:
    def __init__(self, session: Session):
        self.session = session

    def create(self, token_hash: str, user_id: int, expires_at: datetime):
        self.session.add(LoginSession(token_hash=token_hash, user_id=user_id, expires_at=expires_at))

    def find_user(self, token_hash: str, now: datetime) -> User | None:
        return self.session.scalar(
            select(User).join(LoginSession, LoginSession.user_id == User.id).where(
                LoginSession.token_hash == token_hash, LoginSession.expires_at > now
            )
        )
