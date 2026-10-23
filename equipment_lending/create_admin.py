"""Create an administrator locally; public registration always creates members."""
import argparse

from equipment_lending.database import SessionLocal
from equipment_lending.schema.authentication import RegisterRequest
from equipment_lending.service.authentication_service import AuthenticationService, EmailAlreadyRegistered

DEFAULT_PASSWORD = "Admin123!"


def main():
    parser = argparse.ArgumentParser(description="Create an administrator account after initializing the database.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()
    data = RegisterRequest(name=args.name, email=args.email, password=args.password)
    with SessionLocal() as session:
        try:
            user = AuthenticationService(session).register(data.name, str(data.email), data.password, role="admin")
        except EmailAlreadyRegistered:
            parser.error("An account already exists for this email address.")
    print(f"Administrator created: {user.email} (password: {args.password})")


if __name__ == "__main__":
    main()
