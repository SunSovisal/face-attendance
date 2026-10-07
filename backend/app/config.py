"""Settings loaded from backend/.env."""
from pathlib import Path
import os

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def env_value(name: str, default: str | None = None) -> str:
    # A CRLF .env leaves a carriage return on the value, which makes SQLite
    # open a different file named "app.db\r".
    if name in os.environ:
        value = os.environ[name]
    elif default is not None:
        value = default
    else:
        raise KeyError(name)
    return value.replace("\r", "").strip()


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
    secret_key = env_value("SECRET_KEY")
    admin_username = env_value("ADMIN_USERNAME", "admin")
    admin_password = env_value("ADMIN_PASSWORD")
    app_timezone = env_value("APP_TIMEZONE", "Asia/Phnom_Penh")
    weights_path = resolve_path(env_value("WEIGHTS_PATH", "../best.pt"))
    database_url = sqlite_url(env_value("DATABASE_URL", "sqlite:///../data/app.db"))
    faces_dir = resolve_path(env_value("FACES_DIR", "../data/faces"))
    attendance_dir = resolve_path(env_value("ATTENDANCE_DIR", "../data/attendance"))
    known_dir = resolve_path(env_value("KNOWN_DIR", "../known_faces"))
    match_threshold = float(env_value("MATCH_THRESHOLD", "0.50"))
    auto_match_threshold = float(env_value("AUTO_MATCH_THRESHOLD", "0.40"))
    det_conf = float(env_value("DET_CONF", "0.45"))
    match_token_seconds = int(env_value("MATCH_TOKEN_SECONDS", "20"))
    punch_cooldown_seconds = int(env_value("PUNCH_COOLDOWN_SECONDS", "45"))
    undo_seconds = int(env_value("UNDO_SECONDS", "8"))


settings = Settings()