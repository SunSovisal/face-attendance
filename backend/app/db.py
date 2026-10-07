"""SQLAlchemy engine, sessions, and the one-time upgrade from the old tables."""
import shutil
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def enable_sqlite(dbapi_conn, _connection_record):
    # pysqlite starts its own transaction on the first statement. Leave
    # transaction control to SQLAlchemy so a pooled connection cannot keep
    # a write lock after the request ends.
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


@event.listens_for(engine, "begin")
def begin_sqlite(connection):
    connection.exec_driver_sql("BEGIN")


def database_path() -> Path | None:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        return None
    return Path(settings.database_url[len(prefix) :])


def table_names(connection) -> set[str]:
    rows = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    return {row[0] for row in rows}


def backup_legacy_database() -> None:
    path = database_path()
    if path is None or not path.exists():
        return
    with engine.connect() as connection:
        names = table_names(connection)
    if "admins" not in names or "users" in names:
        return
    backup = path.with_name(path.name + ".pre-hr")
    if backup.exists():
        return
    shutil.copy2(path, backup)
    print("Backed up database to", backup)


def rename_legacy_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        names = table_names(connection)
        if "admins" not in names or "users" in names:
            return
        for old in ("admins", "people", "face_samples", "attendance"):
            if old in names:
                connection.execute(text(f"ALTER TABLE {old} RENAME TO {old}_legacy"))


def copy_legacy() -> None:
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        names = table_names(connection)
        if "admins_legacy" not in names:
            return
        users = connection.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        if users:
            return
        admin_rows = connection.execute(
            text("SELECT id, username, password_hash FROM admins_legacy")
        ).fetchall()
        for row in admin_rows:
            role = "super_admin" if row.username == settings.admin_username else "admin"
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, username, password_hash, role, status)
                    VALUES (:id, :username, :password_hash, :role, 'active')
                    """
                ),
                {
                    "id": row.id,
                    "username": row.username,
                    "password_hash": row.password_hash,
                    "role": role,
                },
            )
        if "people_legacy" in names:
            connection.execute(
                text(
                    """
                    INSERT INTO employees (
                        id, user_id, department_id, employee_code, name, position, status, created_at
                    )
                    SELECT id, NULL, NULL, NULL, name, '', 'active', created_at
                    FROM people_legacy
                    """
                )
            )
        if "face_samples_legacy" in names:
            connection.execute(
                text(
                    """
                    INSERT INTO face_samples (id, employee_id, image_path, embedding, created_at)
                    SELECT id, person_id, image_path, embedding, created_at
                    FROM face_samples_legacy
                    """
                )
            )
        user_ids = {row[0] for row in connection.execute(text("SELECT id FROM users")).fetchall()}
        employee_ids = {row[0] for row in connection.execute(text("SELECT id FROM employees")).fetchall()}
        if "attendance_legacy" in names:
            punches = connection.execute(
                text(
                    """
                    SELECT person_id, person_name, timestamp, local_date, distance, admin_id, snapshot_path
                    FROM attendance_legacy
                    """
                )
            ).fetchall()
            grouped: dict[tuple, list] = {}
            for punch in punches:
                grouped.setdefault((punch.person_id, punch.local_date), []).append(punch)
            for (person_id, local_date), items in grouped.items():
                if not local_date:
                    continue
                items.sort(key=lambda item: item.timestamp or "")
                first = items[0]
                snapshot = next((item.snapshot_path for item in reversed(items) if item.snapshot_path), None)
                employee_id = person_id if person_id in employee_ids else None
                confirmed_by = first.admin_id if first.admin_id in user_ids else None
                connection.execute(
                    text(
                        """
                        INSERT INTO attendance_days (
                            employee_id, employee_name, local_date, check_in_at, check_in_distance,
                            check_in_snapshot, check_in_by, check_in_manual, check_out_manual,
                            status, late_minutes, early_minutes, worked_minutes, note
                        )
                        VALUES (
                            :employee_id, :employee_name, :local_date, :check_in_at, :check_in_distance,
                            :check_in_snapshot, :check_in_by, 0, 0,
                            'incomplete', 0, 0, 0, ''
                        )
                        """
                    ),
                    {
                        "employee_id": employee_id,
                        "employee_name": first.person_name,
                        "local_date": local_date,
                        "check_in_at": first.timestamp,
                        "check_in_distance": first.distance,
                        "check_in_snapshot": snapshot,
                        "check_in_by": confirmed_by,
                    },
                )
        for old in ("attendance_legacy", "face_samples_legacy", "people_legacy", "admins_legacy"):
            if old in names:
                connection.execute(text(f"DROP TABLE {old}"))
        print("Migrated the previous attendance database")


def migrate() -> None:
    backup_legacy_database()
    rename_legacy_tables()
    Base.metadata.create_all(engine)
    copy_legacy()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
