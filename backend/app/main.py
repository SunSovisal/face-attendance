"""FastAPI app entry."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from backend.app import engine as face_engine
from backend.app import models
from backend.app.bootstrap import seed_office, seed_super_admin
from backend.app.config import settings
from backend.app.db import SessionLocal, migrate
from backend.app.engine import IMAGE_EXTS, load_models
from backend.app.gallery import load_gallery
from backend.app.routes.accounts import router as accounts_router
from backend.app.routes.attendance import router as attendance_router
from backend.app.routes.auth import router as auth_router
from backend.app.routes.corrections import router as corrections_router
from backend.app.routes.employees import add_photo
from backend.app.routes.employees import router as employees_router
from backend.app.routes.holidays import router as holidays_router
from backend.app.routes.leave import router as leave_router
from backend.app.routes.office import router as office_router
from backend.app.routes.recognize import router as recognize_router


def seed_known_faces(model) -> None:
    db = SessionLocal()
    try:
        if db.query(models.Employee).count() > 0:
            print("Known faces already imported")
            return
        if not settings.known_dir.exists():
            print("No known_faces directory")
            return
        for path in sorted(settings.known_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            employee = models.Employee(name=path.stem)
            db.add(employee)
            db.commit()
            db.refresh(employee)
            try:
                add_photo(db, employee, path.read_bytes(), model)
                print("Seeded:", path.stem)
            except HTTPException as exc:
                db.delete(employee)
                db.commit()
                print("Skipped:", path.name, exc.detail)
    finally:
        db.close()


def create_app() -> FastAPI:
    settings.faces_dir.mkdir(parents=True, exist_ok=True)
    settings.attendance_dir.mkdir(parents=True, exist_ok=True)
    migrate()
    seed_office()
    seed_super_admin()
    app = FastAPI()
    face_engine.WEIGHTS = settings.weights_path
    face_engine.MATCH_THRESHOLD = settings.match_threshold
    face_engine.DET_CONF = settings.det_conf
    app.state.model = load_models()
    seed_known_faces(app.state.model)
    db = SessionLocal()
    try:
        app.state.gallery = load_gallery(db)
    finally:
        db.close()
    app.include_router(auth_router, prefix="/api")
    app.include_router(accounts_router, prefix="/api")
    app.include_router(employees_router, prefix="/api")
    app.include_router(attendance_router, prefix="/api")
    app.include_router(corrections_router, prefix="/api")
    app.include_router(leave_router, prefix="/api")
    app.include_router(holidays_router, prefix="/api")
    app.include_router(office_router, prefix="/api")
    app.include_router(recognize_router, prefix="/api")

    @app.exception_handler(OperationalError)
    async def database_busy(_request, exc: OperationalError):
        if "locked" in str(exc).lower():
            return JSONResponse(
                status_code=503,
                content={"detail": "The database is open in another program. Close it and try again."},
            )
        raise exc

    return app


app = create_app()
