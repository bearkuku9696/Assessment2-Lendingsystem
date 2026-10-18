"""Create an administrator locally; public registration always creates members."""
import argparse
from getpass import getpass

from equipment_lending.database import SessionLocal
from equipment_lending.schema.authentication import RegisterRequest
from equipment_lending.service.authentication_service import AuthenticationService, EmailAlreadyRegistered


def main():
    parser = argparse.ArgumentParser(description="Create an administrator account after initializing the database.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match.")
    data = RegisterRequest(name=args.name, email=args.email, password=password)
    with SessionLocal() as session:
        try:
            user = AuthenticationService(session).register(data.name, str(data.email), data.password, role="admin")
        except EmailAlreadyRegistered:
            parser.error("An account already exists for this email address.")
    print(f"Administrator created: {user.email}")


if __name__ == "__main__":
    main()
