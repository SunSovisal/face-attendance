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
AUTO_MATCH_THRESHOLD=0.40
DET_CONF=0.45
MATCH_TOKEN_SECONDS=20
PUNCH_COOLDOWN_SECONDS=45
UNDO_SECONDS=8
```

`ADMIN_USERNAME` and `ADMIN_PASSWORD` are the super admin, stored only when that account is first created. Changing the password later in `.env` does not update the existing account. To apply a new password, delete that user in `data/app.db` and start the API again. There is only one super admin. Other people register from the sign-in page, and the super admin can promote them.

`MATCH_THRESHOLD` is a cosine distance. A face is recognized when the distance is **0.50 or lower**. Lower means a closer match. At or below `AUTO_MATCH_THRESHOLD` the desk punches on its own. Between that and `MATCH_THRESHOLD` someone still confirms. After a punch the same person is held for `PUNCH_COOLDOWN_SECONDS` and until they leave the frame. **Undo** stays up for `UNDO_SECONDS`.

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

Sign in, or register an employee account. A new registration stays pending until an admin activates it and adds a photo with exactly one face.

- **Live** is the desk. A clear match checks in or out on its own and can be undone for a few seconds. A close match still asks you to confirm. The punch stores the current frame.
- **Today** and **Month** summarize the office. **Attendance** lists each workday, including absences. Admins can correct a time if they record a reason, and employees can request that correction. Both lists download as CSV.
- **Password**, in the sidebar, changes your own password. The super admin can set a password on Accounts. An admin can set an employee's password on Employees.
- **Employees** is the roster, departments, and face photos. Someone already enrolled can get a login from their row.
- **Leave** and **Holidays** decide which days are not absences.
- **Accounts** and **Office hours** are for the super admin. Accounts promotes an employee to admin or demotes them. Office hours are the one schedule used for late and absent.

Employees only see their own attendance and their leave requests. The product rules are in `SCOPE.md`.

Uploaded photos and the SQLite database live under `data/`, which is not committed.

## Webcam script

`python detect.py` still runs the original local webcam window. From the repo root:

```bash
source .venv/bin/activate
PYTHONPATH=. python detect.py
```

That script writes `attendance_log.csv`. The website does not read that file.
