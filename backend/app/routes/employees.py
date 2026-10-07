"""Roster, face photos, and logins for people who were enrolled from a photo."""
import shutil
from pathlib import Path
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.engine import crop_with_pad, decode_jpeg, detect_faces, embed_bgr
from backend.app.gallery import load_gallery
from backend.app.models import Department, Employee, FaceSample, User
from backend.app.routes.auth import clean_username
from backend.app.schemas import AccountCreate, DepartmentCreate, EmployeeUpdate, PasswordSet
from backend.app.security import hash_password, password_problem, require_staff, require_super

router = APIRouter()
employee_router = APIRouter(prefix="/employees")
department_router = APIRouter(prefix="/departments")


def remember(request: Request, db: Session) -> None:
    request.app.state.gallery = load_gallery(db)


def photo_ids(db: Session) -> dict[int, list[int]]:
    rows = db.query(FaceSample.employee_id, FaceSample.id).order_by(FaceSample.id).all()
    grouped: dict[int, list[int]] = {}
    for employee_id, sample_id in rows:
        grouped.setdefault(employee_id, []).append(sample_id)
    return grouped


def employee_out(employee: Employee, photos: list[int]) -> dict:
    user = employee.user
    department = employee.department
    created = employee.created_at.isoformat() if employee.created_at is not None else None
    return {
        "id": employee.id,
        "name": employee.name,
        "employee_code": employee.employee_code,
        "position": employee.position,
        "status": employee.status,
        "department_id": employee.department_id,
        "department_name": department.name if department is not None else "",
        "sample_count": len(photos),
        "photos": photos,
        "user_id": user.id if user is not None else None,
        "username": user.username if user is not None else None,
        "role": user.role if user is not None else None,
        "account_status": user.status if user is not None else None,
        "created_at": created,
    }


def one_out(db: Session, employee: Employee) -> dict:
    db.refresh(employee)
    ids = [
        row.id
        for row in db.query(FaceSample.id).filter(FaceSample.employee_id == employee.id).order_by(FaceSample.id).all()
    ]
    return employee_out(employee, ids)


def cv2_imwrite(path, image) -> bool:
    import cv2

    return bool(cv2.imwrite(str(path), image))


def add_photo(db: Session, employee: Employee, raw: bytes, model) -> None:
    image = decode_jpeg(raw)
    if image is None:
        raise HTTPException(status_code=400, detail="Unreadable image")
    boxes = detect_faces(model, image)
    if len(boxes) != 1:
        raise HTTPException(status_code=400, detail=f"Expected 1 face, found {len(boxes)}")
    embedding = embed_bgr(crop_with_pad(image, boxes[0]))
    if embedding is None:
        raise HTTPException(status_code=400, detail="Could not embed the face")

    folder = settings.faces_dir / str(employee.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}.jpg"
    if not cv2_imwrite(path, image):
        raise HTTPException(status_code=400, detail="Could not save the image")

    db.add(
        FaceSample(
            employee_id=employee.id,
            image_path=str(path),
            embedding=np.asarray(embedding, dtype=np.float32).tobytes(),
        )
    )
    db.commit()
    db.refresh(employee)


def clean_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip()
    if not code:
        return None
    if len(code) > 40:
        raise HTTPException(status_code=400, detail="Employee code is too long")
    return code


def require_code_free(db: Session, code: str | None, employee_id: int | None) -> None:
    if code is None:
        return
    taken = db.query(Employee).filter(Employee.employee_code == code).one_or_none()
    if taken is not None and taken.id != employee_id:
        raise HTTPException(status_code=409, detail="That employee code is already used")


def require_department(db: Session, department_id: int | None) -> None:
    if department_id is None:
        return
    if db.get(Department, department_id) is None:
        raise HTTPException(status_code=400, detail="Department not found")


def require_name_free(db: Session, name: str, employee_id: int | None) -> None:
    taken = db.query(Employee).filter(func.lower(Employee.name) == name.lower()).first()
    if taken is not None and taken.id != employee_id:
        raise HTTPException(status_code=409, detail="That name is already on the roster")


def parse_department(value: str) -> int | None:
    if not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Department not found") from None


@department_router.get("")
def list_departments(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    rows = db.query(Department).order_by(Department.name).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@department_router.post("", status_code=status.HTTP_201_CREATED)
def create_department(body: DepartmentCreate, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    name = body.name.strip()
    if not name or len(name) > 120:
        raise HTTPException(status_code=400, detail="Department name is required")
    if db.query(Department).filter(func.lower(Department.name) == name.lower()).one_or_none():
        raise HTTPException(status_code=409, detail="That department already exists")
    row = Department(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name}


@department_router.delete("/{department_id}")
def delete_department(department_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    row = db.get(Department, department_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@employee_router.get("")
def list_employees(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    employees = (
        db.query(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.department))
        .order_by(Employee.name)
        .all()
    )
    photos = photo_ids(db)
    return [employee_out(employee, photos.get(employee.id, [])) for employee in employees]


@employee_router.post("", status_code=status.HTTP_201_CREATED)
async def create_employee(
    request: Request,
    name: str = Form(...),
    employee_code: str = Form(""),
    position: str = Form(""),
    department_id: str = Form(""),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 120:
        raise HTTPException(status_code=400, detail="Name is required")
    require_name_free(db, cleaned, None)
    code = clean_code(employee_code)
    require_code_free(db, code, None)
    dept_id = parse_department(department_id)
    require_department(db, dept_id)
    employee = Employee(name=cleaned, employee_code=code, position=position.strip()[:120], department_id=dept_id)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    if photo is not None and photo.filename:
        try:
            add_photo(db, employee, await photo.read(), request.app.state.model)
        except HTTPException:
            db.delete(employee)
            db.commit()
            raise
        remember(request, db)
    return one_out(db, employee)


@employee_router.patch("/{employee_id}")
def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name or len(name) > 120:
            raise HTTPException(status_code=400, detail="Name is required")
        require_name_free(db, name, employee.id)
        employee.name = name
    if "employee_code" in data:
        code = clean_code(data["employee_code"])
        require_code_free(db, code, employee.id)
        employee.employee_code = code
    if "position" in data:
        employee.position = (data["position"] or "").strip()[:120]
    if "department_id" in data:
        require_department(db, data["department_id"])
        employee.department_id = data["department_id"]
    if "status" in data:
        if data["status"] not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="Status must be active or inactive")
        employee.status = data["status"]
    db.commit()
    remember(request, db)
    return one_out(db, employee)


@employee_router.get("/{employee_id}/photo")
def employee_photo(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    sample = (
        db.query(FaceSample)
        .filter(FaceSample.employee_id == employee_id)
        .order_by(FaceSample.id.desc())
        .first()
    )
    if sample is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = face_file(sample)
    if path is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})


def face_file(sample: FaceSample) -> Path | None:
    root = settings.faces_dir.resolve()
    path = Path(sample.image_path).resolve()
    if path.is_file() and root in path.parents:
        return path
    return None


@employee_router.get("/{employee_id}/photos/{sample_id}")
def employee_sample(
    employee_id: int,
    sample_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    sample = db.get(FaceSample, sample_id)
    if sample is None or sample.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = face_file(sample)
    if path is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})


@employee_router.delete("/{employee_id}/photos/{sample_id}")
def delete_employee_photo(
    employee_id: int,
    sample_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_super),
):
    sample = db.get(FaceSample, sample_id)
    if sample is None or sample.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = face_file(sample)
    db.delete(sample)
    db.commit()
    if path is not None:
        path.unlink(missing_ok=True)
    remember(request, db)
    return {"ok": True}


@employee_router.post("/{employee_id}/photos", status_code=status.HTTP_201_CREATED)
async def add_employee_photo(
    employee_id: int,
    request: Request,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    add_photo(db, employee, await photo.read(), request.app.state.model)
    remember(request, db)
    return one_out(db, employee)


@employee_router.post("/{employee_id}/activate")
def activate_employee(employee_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    employee = db.get(Employee, employee_id)
    if employee is None or employee.user is None:
        raise HTTPException(status_code=404, detail="Employee account not found")
    if employee.user.role == "super_admin":
        raise HTTPException(status_code=400, detail="The super admin account cannot be changed")
    if employee.user.status != "pending":
        raise HTTPException(status_code=400, detail="Only a pending account can be activated here")
    employee.user.status = "active"
    db.commit()
    remember(request, db)
    return one_out(db, employee)


@employee_router.post("/{employee_id}/account", status_code=status.HTTP_201_CREATED)
def create_login(
    employee_id: int,
    body: AccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if employee.user_id is not None:
        raise HTTPException(status_code=409, detail="This employee already has a login")
    username = clean_username(body.username)
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if db.query(User).filter(User.username == username).one_or_none():
        raise HTTPException(status_code=409, detail="That username is already taken")
    user = User(username=username, password_hash=hash_password(body.password), role="employee", status="active")
    db.add(user)
    db.flush()
    employee.user_id = user.id
    db.commit()
    remember(request, db)
    return one_out(db, employee)


@employee_router.post("/{employee_id}/password")
def reset_employee_password(
    employee_id: int,
    body: PasswordSet,
    db: Session = Depends(get_db),
    actor: User = Depends(require_staff),
):
    employee = db.get(Employee, employee_id)
    if employee is None or employee.user is None:
        raise HTTPException(status_code=404, detail="This employee has no login")
    account = employee.user
    if account.role == "super_admin" or account.id == actor.id:
        raise HTTPException(status_code=400, detail="Change that password from the Password page")
    if account.role != "employee" and actor.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only the super admin can reset an admin password")
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    account.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@employee_router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    linked = employee.user
    if linked is not None and linked.role == "super_admin":
        raise HTTPException(status_code=400, detail="The super admin cannot be deleted")
    folder = settings.faces_dir / str(employee.id)
    if folder.is_dir():
        shutil.rmtree(folder)
    role = linked.role if linked is not None else None
    db.delete(employee)
    db.flush()
    if linked is not None and role == "employee":
        db.delete(linked)
    db.commit()
    remember(request, db)
    return {"ok": True}


router.include_router(employee_router)
router.include_router(department_router)
