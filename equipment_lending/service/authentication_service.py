from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from equipment_lending.dao.login_session_dao import LoginSessionDao
from equipment_lending.dao.user_dao import UserDao


password_hasher = PasswordHash.recommended()
# Perform a password check for unknown accounts too, reducing timing differences.
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
TOKEN_LIFETIME_SECONDS = 24 * 60 * 60


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidToken(Exception):
    pass


class AuthenticationService:
    def __init__(self, session: Session):
        self.session = session
        self.users = UserDao(session)
        self.tokens = LoginSessionDao(session)

    def register(self, name: str, email: str, password: str, role: str = "member"):
        hashed_password = password_hasher.hash(password)
        try:
            with self.session.begin():
                if self.users.find_by_email(email):
                    raise EmailAlreadyRegistered
                user = self.users.create(name, email, hashed_password, role)
        except IntegrityError:
            # The unique constraint also rejects concurrent registrations.
            # Report an email conflict only when that account actually exists.
            if self.users.find_by_email(email):
                raise EmailAlreadyRegistered from None
            raise
        return user

    def login(self, email: str, password: str):
        with self.session.begin():
            user = self.users.find_by_email(email)
            valid = password_hasher.verify(password, user.password_hash if user else dummy_hash)
            if not valid or user is None:
                raise InvalidCredentials
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=TOKEN_LIFETIME_SECONDS)
            self.tokens.create(sha256(token.encode()).hexdigest(), user.id, expires_at)
        return token, user

    def current_user(self, token: str):
        with self.session.begin():
            user = self.tokens.find_user(
                sha256(token.encode()).hexdigest(), datetime.now(UTC).replace(tzinfo=None)
            )
            if user is None:
                raise InvalidToken
        return user

    def logout(self, token: str):
        token_hash = sha256(token.encode()).hexdigest()
        with self.session.begin():
            if self.tokens.find_user(token_hash, datetime.now(UTC).replace(tzinfo=None)) is None:
                raise InvalidToken
            self.tokens.delete(token_hash)
