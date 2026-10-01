"""Password hashing and JWT cookie auth."""
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models import Admin

hasher = PasswordHash.recommended()
COOKIE = "access_token"
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(password, encoded)
    except Exception:
        return False


def create_access_token(admin_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode(
        {"sub": str(admin_id), "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def read_admin_id(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, ValueError, TypeError):
        return None


def get_current_admin(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Admin:
    admin_id = read_admin_id(access_token) if access_token else None
    admin = db.get(Admin, admin_id) if admin_id is not None else None
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return admin