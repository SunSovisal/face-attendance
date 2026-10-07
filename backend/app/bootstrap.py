"""Create the office row and the single super admin."""
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.models import User
from backend.app.security import hash_password
from backend.app.sheet import get_office


def seed_office() -> None:
    db: Session = SessionLocal()
    try:
        get_office(db)
    finally:
        db.close()


def seed_super_admin() -> None:
    db: Session = SessionLocal()
    try:
        if db.query(User).filter(User.role == "super_admin").first() is not None:
            return
        user = db.query(User).filter(User.username == settings.admin_username).one_or_none()
        if user is None:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    role="super_admin",
                    status="active",
                )
            )
        else:
            user.role = "super_admin"
            user.status = "active"
        db.commit()
    finally:
        db.close()
