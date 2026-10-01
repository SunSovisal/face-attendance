"""Admin, Person, FaceSample, and Attendance models."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    samples: Mapped[list["FaceSample"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )


class FaceSample(Base):
    __tablename__ = "face_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    image_path: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    person: Mapped[Person] = relationship(back_populates="samples")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("person_id", "local_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    person_name: Mapped[str] = mapped_column(String(120))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_date: Mapped[str] = mapped_column(String(10), index=True)
    distance: Mapped[float] = mapped_column(Float)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"))