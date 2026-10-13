from werkzeug.security import check_password_hash, generate_password_hash

from ..dao import UserDao
from .exceptions import ValidationError


class AuthenticationService:
    def __init__(self, user_dao=None):
        self.user_dao = user_dao or UserDao()

    def find_user(self, user_id):
        return self.user_dao.find_by_id(user_id)

    def register(self, name, email, password):
        name = name.strip()
        email = email.strip().lower()
        if not name or not email or not password:
            raise ValidationError("Name, email, and password are required.")
        if len(password) < 8:
            raise ValidationError("Password must contain at least 8 characters.")
        if self.user_dao.find_by_email(email):
            raise ValidationError("An account already exists for this email address.")
        return self.user_dao.create(name, email, generate_password_hash(password))

    def authenticate(self, email, password):
        user = self.user_dao.find_by_email(email.strip().lower())
        if user is None or not check_password_hash(user["password_hash"], password):
            raise ValidationError("Invalid email address or password.")
        return user
