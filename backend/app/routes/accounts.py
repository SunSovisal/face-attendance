"""Super admin account controls."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from backend.app.db import get_db
from backend.app.gallery import load_gallery
from backend.app.models import User
from backend.app.routes.auth import public_user
from backend.app.schemas import PasswordSet
from backend.app.security import hash_password, password_problem, require_super

router = APIRouter(prefix="/accounts")


def remember(request: Request, db: Session) -> None:
    request.app.state.gallery = load_gallery(db)


def reject_owner(user: User) -> None:
    if user.role == "super_admin":
        raise HTTPException(status_code=400, detail="The super admin account cannot be changed")


@router.get("")
def list_accounts(db: Session = Depends(get_db), _: User = Depends(require_super)):
    users = db.query(User).options(joinedload(User.employee)).all()
    order = {"super_admin": 0, "admin": 1, "employee": 2}
    users.sort(key=lambda user: (order.get(user.role, 9), user.username.lower()))
    return [public_user(user) for user in users]


@router.post("/{user_id}/activate")
def activate(user_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(require_super)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    reject_owner(user)
    if user.status == "active":
        raise HTTPException(status_code=400, detail="Account is already active")
    user.status = "active"
    db.commit()
    db.refresh(user)
    remember(request, db)
    return public_user(user)


@router.post("/{user_id}/disable")
def disable(user_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_super)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    reject_owner(user)
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")
    if user.status == "disabled":
        raise HTTPException(status_code=400, detail="Account is already disabled")
    user.status = "disabled"
    db.commit()
    db.refresh(user)
    remember(request, db)
    return public_user(user)


@router.post("/{user_id}/promote")
def promote(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_super)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if user.role != "employee" or user.status != "active":
        raise HTTPException(status_code=400, detail="Only an active employee can be promoted")
    user.role = "admin"
    db.commit()
    db.refresh(user)
    return public_user(user)


@router.post("/{user_id}/password")
def reset_password(user_id: int, body: PasswordSet, db: Session = Depends(get_db), actor: User = Depends(require_super)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    reject_owner(user)
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="Change your password from the Password page")
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    user.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/demote")
def demote(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_super)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if user.role != "admin":
        raise HTTPException(status_code=400, detail="Only an admin can be demoted")
    user.role = "employee"
    db.commit()
    db.refresh(user)
    return public_user(user)
