"""In-memory face gallery."""
import numpy as np
from sqlalchemy.orm import Session, joinedload

from backend.app.models import Employee


def load_gallery(db: Session) -> dict:
    gallery = {}
    employees = (
        db.query(Employee)
        .options(joinedload(Employee.user), joinedload(Employee.samples), joinedload(Employee.department))
        .all()
    )
    for employee in employees:
        embeddings = [np.frombuffer(sample.embedding, dtype=np.float32).copy() for sample in employee.samples]
        if employee.is_matchable(bool(embeddings)):
            department = employee.department
            gallery[employee.id] = {
                "name": employee.name,
                "embeddings": embeddings,
                "employee_code": employee.employee_code or "",
                "position": employee.position or "",
                "department": department.name if department is not None else "",
            }
    return gallery
