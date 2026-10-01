"""In-memory face gallery."""
import numpy as np
from sqlalchemy.orm import Session

from backend.app.models import Person


def load_gallery(db: Session) -> dict:
    gallery = {}
    for person in db.query(Person).all():
        embeddings = [
            np.frombuffer(sample.embedding, dtype=np.float32).copy()
            for sample in person.samples
        ]
        if embeddings:
            gallery[person.id] = {"name": person.name, "embeddings": embeddings}
    return gallery