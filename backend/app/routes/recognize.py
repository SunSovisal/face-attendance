"""Live recognition WebSocket."""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.db import SessionLocal
from backend.app.desk import match_band, note_seen, punch_blocked
from backend.app.engine import decode_jpeg, recognize_frame
from backend.app.models import User
from backend.app.security import COOKIE, STAFF, read_user_id
from backend.app.sheet import punch_target
from backend.app.tokens import issue_match_token
from backend.app.workday import local_now

router = APIRouter()
SMOOTH_ALPHA = 0.25
SMOOTH_STEP = 0.05
SMOOTH_HOLD = 2


def staff_id_from_socket(websocket: WebSocket) -> int | None:
    token = websocket.cookies.get(COOKIE)
    user_id = read_user_id(token) if token else None
    if user_id is None:
        return None
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None or user.status != "active" or user.role not in STAFF:
            return None
        return user.id
    finally:
        db.close()


def actions_for(employee_ids: list[int]) -> dict[int, str]:
    if not employee_ids:
        return {}
    today = local_now().date()
    db = SessionLocal()
    try:
        return {employee_id: punch_target(db, employee_id, today)[1] for employee_id in employee_ids}
    finally:
        db.close()


def smooth_matches(history: dict, faces: list[dict]) -> None:
    """Hold the shown distance steady while the raw score chatters inside one band."""
    seen: set[int] = set()
    for face in faces:
        if not face.get("matched") or face.get("person_id") is None:
            continue
        employee_id = int(face["person_id"])
        seen.add(employee_id)
        state = history.setdefault(employee_id, {"ema": None, "missed": 0})
        sample = float(face["distance"])
        previous = state["ema"]
        state["ema"] = sample if previous is None else (1 - SMOOTH_ALPHA) * previous + SMOOTH_ALPHA * sample
        state["missed"] = 0
        face["distance"] = round(round(state["ema"] / SMOOTH_STEP) * SMOOTH_STEP, 2)
    for employee_id in list(history):
        if employee_id in seen:
            continue
        history[employee_id]["missed"] += 1
        if history[employee_id]["missed"] > SMOOTH_HOLD:
            del history[employee_id]


def run_frame(app, user_id: int, raw: bytes, history: dict | None = None) -> dict:
    image = decode_jpeg(raw)
    if image is None:
        return {"frame_width": 0, "frame_height": 0, "faces": []}

    height, width = image.shape[:2]
    recognized = recognize_frame(app.state.model, image, app.state.gallery)
    if history is not None:
        smooth_matches(history, recognized)
    seen = {
        int(face["person_id"])
        for face in recognized
        if face.get("matched") and face.get("person_id") is not None
    }
    note_seen(seen)
    matched_ids = [int(face["person_id"]) for face in recognized if face.get("person_id") is not None]
    actions = actions_for(matched_ids)
    faces = []
    for face in recognized:
        employee_id = int(face["person_id"]) if face.get("person_id") is not None else None
        action = actions.get(employee_id, "check_in") if employee_id is not None else None
        profile = app.state.gallery.get(employee_id, {}) if employee_id is not None else {}
        blocked = employee_id is not None and punch_blocked(employee_id)
        band = match_band(float(face["distance"])) if face["matched"] and not face.get("spoof") else None
        item = {
            "box": [int(value) for value in face["box"]],
            "employee_id": employee_id,
            "name": face["name"],
            "distance": float(face["distance"]),
            "matched": bool(face["matched"]),
            "spoof": bool(face.get("spoof")),
            "confidence": band,
            "held": blocked,
            "action": action,
            "employee_code": profile.get("employee_code") or "",
            "position": profile.get("position") or "",
            "department": profile.get("department") or "",
        }
        if face["matched"] and not face.get("spoof") and employee_id is not None and action != "done" and not blocked:
            item["match_token"] = issue_match_token(user_id, employee_id, float(face["distance"]))
        faces.append(item)
    return {"frame_width": int(width), "frame_height": int(height), "faces": faces}


@router.websocket("/recognize")
async def recognize(websocket: WebSocket):
    user_id = staff_id_from_socket(websocket)
    if user_id is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    # Only the newest unread frame is kept. A frame that arrives while
    # ArcFace is running replaces the previous unread one.
    latest = {"frame": None, "closed": False}
    history: dict = {}

    async def consume():
        try:
            while True:
                latest["frame"] = await websocket.receive_bytes()
        except WebSocketDisconnect:
            latest["closed"] = True

    async def infer():
        while not latest["closed"]:
            frame = latest["frame"]
            if frame is None:
                await asyncio.sleep(0.02)
                continue
            latest["frame"] = None
            payload = await asyncio.to_thread(run_frame, websocket.app, user_id, frame, history)
            if latest["closed"]:
                return
            await websocket.send_json(payload)

    reader = asyncio.create_task(consume())
    try:
        await infer()
    finally:
        reader.cancel()
