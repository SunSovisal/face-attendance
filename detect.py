from pathlib import Path
from datetime import datetime
import csv
import cv2

from backend.app.engine import enroll_directory, load_models, recognize_frame

KNOWN_DIR = Path("known_faces")
ATTENDANCE_CSV = Path("attendance_log.csv")
CAMERA_INDEX = 0
FRAME_STRIDE = 8
STICKY_SECONDS = 3.0


def log_attendance(name, seen):
    if name == "Unknown" or name in seen:
        return
    seen.add(name)
    new_file = not ATTENDANCE_CSV.exists()
    with ATTENDANCE_CSV.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["name", "timestamp"])
        w.writerow([name, datetime.now().isoformat(timespec="seconds")])
    print("ATTENDANCE:", name)


def main():
    model = load_models()
    gallery = enroll_directory(KNOWN_DIR)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam")

    seen = set()
    sticky = {}
    frame_idx = 0
    last_labels = []

    print("Press Q to quit")
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        now = datetime.now().timestamp()

        if frame_idx % FRAME_STRIDE == 0:
            last_labels = []
            for face in recognize_frame(model, frame, gallery):
                name = face["name"]
                dist = face["distance"]
                if face.get("spoof"):
                    label = "Photo"
                elif name != "Unknown":
                    sticky[name] = now
                    log_attendance(name, seen)
                    label = f"{name} ({dist:.2f})"
                else:
                    for n, t in list(sticky.items()):
                        if now - t <= STICKY_SECONDS:
                            name, dist = n, dist
                            break
                    label = f"{name} ({dist:.2f})" if name != "Unknown" else "Unknown"
                last_labels.append((face["box"], label))

        for (x1, y1, x2, y2), label in last_labels:
            color = (0, 200, 0) if "Unknown" not in label and label != "Photo" else (0, 0, 220)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        cv2.imshow("Face Attendance", frame)
        frame_idx += 1
        if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Log:", ATTENDANCE_CSV.resolve())


if __name__ == "__main__":
    main()