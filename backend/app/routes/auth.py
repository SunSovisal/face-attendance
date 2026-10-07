"""Register, login, logout, and the current user."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Employee, User
from backend.app.schemas import LoginRequest, PasswordChange, RegisterRequest
from backend.app.security import (
    COOKIE,
    create_access_token,
    get_current_user,
    hash_password,
    password_problem,
    verify_password,
)

router = APIRouter(prefix="/auth")


def public_user(user: User) -> dict:
    employee = user.employee
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "employee_id": employee.id if employee is not None else None,
        "employee_name": employee.name if employee is not None else None,
    }


def set_login_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=COOKIE,
        value=create_access_token(user_id),
        httponly=True,
        samesite="lax",
        path="/",
        max_age=12 * 60 * 60,
        secure=False,
    )


def clean_username(value: str) -> str:
    username = value.strip()
    if not username or any(char.isspace() for char in username) or len(username) > 80:
        raise HTTPException(status_code=400, detail="Username cannot contain spaces")
    return username


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    name = body.full_name.strip()
    if not name or len(name) > 120:
        raise HTTPException(status_code=400, detail="Name is required")
    username = clean_username(body.username)
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if db.query(User).filter(User.username == username).one_or_none():
        raise HTTPException(status_code=409, detail="That username is already taken")
    taken = db.query(Employee).filter(func.lower(Employee.name) == name.lower()).first()
    if taken is not None:
        raise HTTPException(
            status_code=409,
            detail="That name is already on the roster. An admin can create a login for them.",
        )
    user = User(username=username, password_hash=hash_password(body.password), role="employee", status="pending")
    db.add(user)
    db.flush()
    db.add(Employee(user_id=user.id, name=name, status="active"))
    db.commit()
    db.refresh(user)
    set_login_cookie(response, user.id)
    return public_user(user)


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if user.status == "disabled":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is disabled")
    set_login_cookie(response, user.id)
    return public_user(user)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return public_user(user)


@router.post("/password")
def change_password(body: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is wrong")
    problem = password_problem(body.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Choose a different password")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
