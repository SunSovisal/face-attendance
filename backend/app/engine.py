"""YOLO detection and ArcFace matching."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from deepface import DeepFace
from ultralytics import YOLO

DET_CONF = 0.45
MATCH_THRESHOLD = 0.50
MODEL_NAME = "ArcFace"
CROP_PAD = 0.25
WEIGHTS = Path(__file__).resolve().parents[2] / "best.pt"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_spoof = None


def l2_normalize(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x) + 1e-8)


def cosine_distance(a, b) -> float:
    return float(1.0 - np.dot(l2_normalize(a), l2_normalize(b)))


def embed_bgr(img_bgr):
    try:
        reps = DeepFace.represent(
            img_path=img_bgr,
            model_name=MODEL_NAME,
            detector_backend="skip",
            enforce_detection=False,
        )
        return np.array(reps[0]["embedding"], dtype=np.float32)
    except Exception:
        return None


def detect_faces(model, frame):
    res = model.predict(frame, conf=DET_CONF, verbose=False)[0]
    boxes = []
    if res.boxes is None:
        return boxes
    h, w = frame.shape[:2]
    for b in res.boxes.xyxy.cpu().numpy():
        x1, y1, x2, y2 = map(int, b)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        if x2 > x1 and y2 > y1:
            boxes.append((x1, y1, x2, y2))
    return boxes


def crop_with_pad(frame, box, pad=CROP_PAD):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    x1 = max(0, int(x1 - bw * pad))
    y1 = max(0, int(y1 - bh * pad))
    x2 = min(w, int(x2 + bw * pad))
    y2 = min(h, int(y2 + bh * pad))
    return frame[y1:y2, x1:x2]


def decode_jpeg(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def match_embedding(emb, gallery):
    best_id, best_name, best_dist = None, "Unknown", 1e9
    for person_id, entry in gallery.items():
        for ref in entry["embeddings"]:
            dist = cosine_distance(emb, ref)
            if dist < best_dist:
                best_id, best_name, best_dist = person_id, entry["name"], dist
    if best_dist <= MATCH_THRESHOLD:
        return best_id, best_name, best_dist
    return None, "Unknown", best_dist


def load_models():
    global _spoof
    from deepface.models.spoofing.FasNet import Fasnet

    model = YOLO(str(WEIGHTS))
    embed_bgr(np.zeros((64, 64, 3), dtype=np.uint8))
    _spoof = Fasnet()
    _spoof.analyze(np.zeros((160, 160, 3), dtype=np.uint8), (40, 40, 80, 80))
    return model


def face_is_live(frame, box) -> tuple[bool, float]:
    """True when MiniFASNet reads the face as a live person, not a photo or screen."""
    if _spoof is None:
        return False, 0.0
    x1, y1, x2, y2 = box
    try:
        is_real, score = _spoof.analyze(frame, (x1, y1, x2 - x1, y2 - y1))
    except Exception:
        return False, 0.0
    return bool(is_real), float(score)


def recognize_frame(model, frame_bgr, gallery):
    faces = []
    for box in detect_faces(model, frame_bgr):
        live, _score = face_is_live(frame_bgr, box)
        if not live:
            faces.append(
                {
                    "box": list(box),
                    "person_id": None,
                    "name": "Unknown",
                    "distance": 10.0,
                    "matched": False,
                    "spoof": True,
                }
            )
            continue
        crop = crop_with_pad(frame_bgr, box)
        emb = embed_bgr(crop)
        if emb is None:
            faces.append(
                {
                    "box": list(box),
                    "person_id": None,
                    "name": "Unknown",
                    "distance": 9.0,
                    "matched": False,
                    "spoof": False,
                }
            )
            continue
        person_id, name, dist = match_embedding(emb, gallery)
        faces.append(
            {
                "box": list(box),
                "person_id": person_id,
                "name": name,
                "distance": dist,
                "matched": person_id is not None,
                "spoof": False,
            }
        )
    return faces

def enroll_directory(known_dir, model):
    gallery = {}
    for p in sorted(Path(known_dir).iterdir()):
        if p.suffix.lower() not in IMAGE_EXTS:
            continue
        img = cv2.imread(str(p))
        if img is None:
            print("Skipped:", p.name, "(unreadable)")
            continue
        boxes = detect_faces(model, img)
        if len(boxes) != 1:
            print("Skipped:", p.name, f"(expected 1 face, found {len(boxes)})")
            continue
        emb = embed_bgr(crop_with_pad(img, boxes[0]))
        if emb is None:
            print("Skipped:", p.name, "(no embedding)")
            continue
        gallery[p.stem] = {"name": p.stem, "embeddings": [emb]}
        print("Enrolled:", p.stem)
    if not gallery:
        raise RuntimeError(f"No faces in {known_dir}")
    return gallery
