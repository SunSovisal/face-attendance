"""FastAPI app entry."""
from fastapi import FastAPI

from backend.app import models
from backend.app.config import settings
from backend.app.db import Base, SessionLocal, engine
from backend.app.engine import load_models
from backend.app.gallery import load_gallery
from backend.app.routes.auth import router as auth_router
from backend.app.routes.people import router as people_router
from backend.app.routes.attendance import router as attendance_router
from backend.app.routes.recognize import router as recognize_router
from backend.app.security import hash_password


def seed_admin() -> None:
    db = SessionLocal()
    try:
        exists = db.query(models.Admin).filter_by(username=settings.admin_username).one_or_none()
        if exists is None:
            db.add(
                models.Admin(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
            db.commit()
    finally:
        db.close()

def seed_known_faces(model) -> None:
    from fastapi import HTTPException

    from backend.app.engine import IMAGE_EXTS
    from backend.app.routes.people import add_photo

    db = SessionLocal()
    try:
        if db.query(models.Person).count() > 0:
            print("Known faces already imported")
            return
        if not settings.known_dir.exists():
            print("No known_faces directory")
            return
        for path in sorted(settings.known_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            person = models.Person(name=path.stem)
            db.add(person)
            db.commit()
            db.refresh(person)
            try:
                add_photo(db, person, path.read_bytes(), model)
                print("Seeded:", path.stem)
            except HTTPException as exc:
                db.delete(person)
                db.commit()
                print("Skipped:", path.name, exc.detail)
    finally:
        db.close()

def create_app() -> FastAPI:
    settings.faces_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    seed_admin()
    app = FastAPI()
    app.state.model = load_models()
    seed_known_faces(app.state.model)
    db = SessionLocal()
    try:
        app.state.gallery = load_gallery(db)
    finally:
        db.close()
    app.include_router(auth_router, prefix="/api")
    app.include_router(people_router, prefix="/api")
    app.include_router(attendance_router, prefix="/api")
    app.include_router(recognize_router, prefix="/api")
    return app


app = create_app()