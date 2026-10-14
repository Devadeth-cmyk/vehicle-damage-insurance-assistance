"""Create the first platform administrator from environment variables.

Run from ``backend`` after installing requirements:
    $env:ADMIN_EMAIL = "admin@example.com"
    $env:ADMIN_PASSWORD = "a-long-unique-password"
    python -m scripts.bootstrap_admin
"""

import os

from sqlalchemy import func

# Import the application bootstrap so existing local databases receive the
# additive columns needed by the current SQLAlchemy models before ORM writes.
from app.main import app as _app  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base, import_models
from app.db.database import SessionLocal, engine
from app.db.models.user import User, UserRole


def main() -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    name = os.getenv("ADMIN_NAME", "AutoInsight Administrator").strip()
    if not email or not password:
        raise SystemExit("Set ADMIN_EMAIL and ADMIN_PASSWORD before running this command.")
    if len(password.encode("utf-8")) < 12 or len(password.encode("utf-8")) > 72:
        raise SystemExit("ADMIN_PASSWORD must be between 12 and 72 UTF-8 bytes.")

    import_models()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if user:
            if user.role != UserRole.ADMIN:
                raise SystemExit("That email already belongs to a non-admin account.")
            print(f"Administrator {email} already exists.")
            return
        db.add(User(
            full_name=name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        ))
        db.commit()
        print(f"Created platform administrator {email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
