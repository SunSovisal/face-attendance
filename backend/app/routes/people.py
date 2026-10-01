"""Enroll and delete people."""
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.engine import crop_with_pad, decode_jpeg, detect_faces, embed_bgr
from backend.app.gallery import load_gallery
from backend.app.models import Admin, FaceSample, Person
from backend.app.security import get_current_admin
import numpy as np

router = APIRouter(prefix="/people")


def person_out(person: Person) -> dict:
    created = person.created_at.isoformat() if person.created_at is not None else None
    return {
        "id": person.id,
        "name": person.name,
        "sample_count": len(person.samples),
        "created_at": created,
    }


def add_photo(db: Session, person: Person, raw: bytes, model) -> None:
    image = decode_jpeg(raw)
    if image is None:
        raise HTTPException(status_code=400, detail="Unreadable image")
    boxes = detect_faces(model, image)
    if len(boxes) != 1:
        raise HTTPException(status_code=400, detail=f"Expected 1 face, found {len(boxes)}")
    embedding = embed_bgr(crop_with_pad(image, boxes[0]))
    if embedding is None:
        raise HTTPException(status_code=400, detail="Could not embed the face")

    folder = settings.faces_dir / str(person.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}.jpg"
    if not cv2_imwrite(path, image):
        raise HTTPException(status_code=400, detail="Could not save the image")

    db.add(
        FaceSample(
            person_id=person.id,
            image_path=str(path),
            embedding=np.asarray(embedding, dtype=np.float32).tobytes(),
        )
    )
    db.commit()
    db.refresh(person)


def cv2_imwrite(path, image) -> bool:
    import cv2

    return bool(cv2.imwrite(str(path), image))


def remember(request: Request, db: Session) -> None:
    request.app.state.gallery = load_gallery(db)


@router.get("")
def list_people(db: Session = Depends(get_db), _: Admin = Depends(get_current_admin)):
    people = db.query(Person).order_by(Person.name).all()
    return [person_out(person) for person in people]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_person(
    request: Request,
    name: str = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Name is required")
    if db.query(Person).filter(Person.name == cleaned).one_or_none():
        raise HTTPException(status_code=409, detail="That name already exists")

    person = Person(name=cleaned)
    db.add(person)
    db.commit()
    db.refresh(person)
    try:
        add_photo(db, person, await photo.read(), request.app.state.model)
    except HTTPException:
        db.delete(person)
        db.commit()
        raise
    remember(request, db)
    db.refresh(person)
    return person_out(person)


@router.post("/{person_id}/photos", status_code=status.HTTP_201_CREATED)
async def add_person_photo(
    person_id: int,
    request: Request,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    add_photo(db, person, await photo.read(), request.app.state.model)
    remember(request, db)
    db.refresh(person)
    return person_out(person)


@router.delete("/{person_id}")
def delete_person(
    person_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    folder = settings.faces_dir / str(person.id)
    if folder.is_dir():
        shutil.rmtree(folder)
    db.delete(person)
    db.commit()
    remember(request, db)
    return {"ok": True}