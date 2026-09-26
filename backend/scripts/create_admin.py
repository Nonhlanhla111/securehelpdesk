"""Create the first Administrator account.

Run from the backend folder:   python -m scripts.create_admin
"""
import getpass
import sys

from sqlalchemy import select

from app.constants import RoleName
from app.database import Base, SessionLocal, engine
from app.models import Role, User
from app.schemas import RegisterRequest
from app.security import hash_password
from app.seed import seed_lookups


def main() -> None:
    Base.metadata.create_all(bind=engine)
    email = input("Admin email: ").strip().lower()
    name = input("Full name: ").strip()
    password = getpass.getpass("Password (min 10 chars, upper+lower+digit): ")
    try:
        RegisterRequest(email=email, full_name=name, password=password)  # reuse the API's validation
    except Exception as exc:
        sys.exit(f"Invalid input: {exc}")
    with SessionLocal() as db:
        seed_lookups(db)
        if db.scalar(select(User).where(User.email == email)):
            sys.exit("A user with that email already exists.")
        role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
        db.add(User(email=email, full_name=name, hashed_password=hash_password(password), role_id=role.id))
        db.commit()
    print(f"Administrator {email} created.")


if __name__ == "__main__":
    main()
