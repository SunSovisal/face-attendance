"""Login, logout, and current admin."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Admin
from backend.app.schemas import LoginRequest
from backend.app.security import (
    COOKIE,
    create_access_token,
    get_current_admin,
    verify_password,
)

router = APIRouter(prefix="/auth")


def set_login_cookie(response: Response, admin_id: int) -> None:
    response.set_cookie(
        key=COOKIE,
        value=create_access_token(admin_id),
        httponly=True,
        samesite="lax",
        path="/",
        max_age=12 * 60 * 60,
        secure=False,
    )


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == body.username).one_or_none()
    if admin is None or not verify_password(body.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    set_login_cookie(response, admin.id)
    return {"id": admin.id, "username": admin.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(admin: Admin = Depends(get_current_admin)):
    return {"id": admin.id, "username": admin.username}