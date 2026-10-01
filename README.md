# Face attendance

A small admin app that recognizes faces from the browser camera and records attendance after you confirm the match.

The Vue app is in `frontend/`. Recognition runs in a FastAPI process that loads `best.pt` and ArcFace.

## Requirements

- Python 3.13
- Node.js 20 or newer
- A webcam for the Live page

`best.pt` must stay in the repo root. Photos in `known_faces/` are imported the first time the database is empty. The filename, without the extension, becomes the person's name.

## Backend

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Create `backend/.env`:

```text
SECRET_KEY=change-me
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
APP_TIMEZONE=Asia/Phnom_Penh
WEIGHTS_PATH=../best.pt
DATABASE_URL=sqlite:///../data/app.db
FACES_DIR=../data/faces
KNOWN_DIR=../known_faces
MATCH_THRESHOLD=0.50
DET_CONF=0.45
MATCH_TOKEN_SECONDS=20
```

`ADMIN_PASSWORD` is stored only when the admin account is first created. Changing it later in `.env` does not update the existing account. To apply a new password, delete the `admins` row in `data/app.db` and start the API again.

`MATCH_THRESHOLD` is a cosine distance. A face is recognized when the distance is **0.50 or lower**. Lower means a closer match.

Start the API from the repo root:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The first start downloads ArcFace weights and can sit for a while before Uvicorn says it is ready. Later starts are faster. Keep this as one process. A second worker loads the models again.

## Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL Vite prints, usually http://127.0.0.1:5173. Sign in with `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `backend/.env`.

The Vite dev server proxies `/api` to port 8000, including the live recognition socket. Both processes need to be running.

## What the pages do

- **People** enrolls one face per photo. A photo with no face or more than one face is rejected.
- **Live** draws boxes on the camera frame. A known face is logged only after you press **Yes**. Each person can be logged once per calendar day in `APP_TIMEZONE`.
- **Attendance** lists those confirmed check-ins.

Uploaded photos and the SQLite database live under `data/`, which is not committed.

## Webcam script

`python detect.py` still runs the original local webcam window. From the repo root:

```bash
source .venv/bin/activate
PYTHONPATH=. python detect.py
```

That script writes `attendance_log.csv`. The website does not read that file.
