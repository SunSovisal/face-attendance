"""Live recognition WebSocket."""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.db import SessionLocal
from backend.app.engine import decode_jpeg, recognize_frame
from backend.app.models import Admin
from backend.app.security import COOKIE, read_admin_id
from backend.app.tokens import issue_match_token

router = APIRouter()


def admin_id_from_socket(websocket: WebSocket) -> int | None:
    token = websocket.cookies.get(COOKIE)
    admin_id = read_admin_id(token) if token else None
    if admin_id is None:
        return None
    db = SessionLocal()
    try:
        admin = db.get(Admin, admin_id)
    finally:
        db.close()
    if admin is None:
        return None
    return admin_id


def run_frame(app, admin_id: int, raw: bytes) -> dict:
    image = decode_jpeg(raw)
    if image is None:
        return {"frame_width": 0, "frame_height": 0, "faces": [], "matches": []}

    height, width = image.shape[:2]
    faces = []
    matches = []
    for face in recognize_frame(app.state.model, image, app.state.gallery):
        item = {
            "box": [int(value) for value in face["box"]],
            "person_id": face["person_id"],
            "name": face["name"],
            "distance": float(face["distance"]),
            "matched": bool(face["matched"]),
        }
        if face["matched"] and face["person_id"] is not None:
            token = issue_match_token(admin_id, int(face["person_id"]), float(face["distance"]))
            item["match_token"] = token
            matches.append(
                {
                    "person_id": int(face["person_id"]),
                    "name": face["name"],
                    "distance": float(face["distance"]),
                    "match_token": token,
                }
            )
        faces.append(item)
    return {"frame_width": int(width), "frame_height": int(height), "faces": faces, "matches": matches}


@router.websocket("/recognize")
async def recognize(websocket: WebSocket):
    admin_id = admin_id_from_socket(websocket)
    if admin_id is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    # Only the newest unread frame is kept. A frame that arrives while
    # ArcFace is running replaces the previous unread one.
    latest = {"frame": None, "closed": False}

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
            payload = await asyncio.to_thread(run_frame, websocket.app, admin_id, frame)
            if latest["closed"]:
                return
            await websocket.send_json(payload)

    reader = asyncio.create_task(consume())
    try:
        await infer()
    finally:
        reader.cancel()