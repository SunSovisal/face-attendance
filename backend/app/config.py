"""Settings loaded from backend/.env."""
from pathlib import Path
import os

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (BACKEND_DIR / path).resolve()


def sqlite_url(value: str) -> str:
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        raise RuntimeError("DATABASE_URL must start with sqlite:///")
    return "sqlite:///" + resolve_path(value[len(prefix) :]).as_posix()


class Settings:
    secret_key = os.environ["SECRET_KEY"]
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ["ADMIN_PASSWORD"]
    app_timezone = os.environ.get("APP_TIMEZONE", "Asia/Phnom_Penh")
    weights_path = resolve_path(os.environ.get("WEIGHTS_PATH", "../best.pt"))
    database_url = sqlite_url(os.environ.get("DATABASE_URL", "sqlite:///../data/app.db"))
    faces_dir = resolve_path(os.environ.get("FACES_DIR", "../data/faces"))
    known_dir = resolve_path(os.environ.get("KNOWN_DIR", "../known_faces"))
    match_threshold = float(os.environ.get("MATCH_THRESHOLD", "0.50"))
    det_conf = float(os.environ.get("DET_CONF", "0.45"))
    match_token_seconds = int(os.environ.get("MATCH_TOKEN_SECONDS", "20"))


settings = Settings()