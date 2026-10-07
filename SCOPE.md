# Face attendance

One office. One camera desk. Employees are recognized by face, and a workday is recorded only after someone at the desk confirms check-in or check-out.

The owner is the only super admin. Other people register their own accounts. The super admin can promote an employee to admin.

## Theme

Quiet desk software. The screen should feel like paper, not a dashboard.

| Token | Value | Use |
| --- | --- | --- |
| Paper | `#f4f4f2` | Page background |
| Panel | `#ffffff` | Cards, header, form surfaces |
| Ink | `#191919` | Text, primary buttons |
| Mute | `#6b6b66` | Secondary text, empty states |
| Line | `#e4e4df` | Borders and dividers |
| Good | `#1d7a4f` | On time, approved, a recognized face |
| Danger | `#b3261e` | Late, absent, unknown face, errors, delete |

- Type is Inter, with the system sans as fallback.
- Cards use a 14px radius and a hairline border. No shadows, gradients, or decorative icons.
- Copy is short and plain. Buttons say what they do.
- Every time and every calendar day uses `Asia/Phnom_Penh`.

## Roles

| | Super admin | Admin | Employee |
| --- | --- | --- | --- |
| How the account appears | Seeded once from `backend/.env`. This is the owner. | Promoted by the super admin | Self-registration |
| How many | Exactly one | As many as the owner promotes | Anyone who registers |
| Live desk, confirm punches | Yes | Yes | No |
| Employees, faces, departments | Yes | Yes | Own profile only |
| Attendance of the office | Yes | Yes | Own days only |
| Leave approval, holidays | Yes | Yes | Request leave only |
| Office hours | Yes | No | No |
| Promote, demote, disable accounts | Yes | No | No |

Rules:

- Registration always creates an employee. It never creates an admin or a second super admin.
- Only the super admin can promote an active employee to admin, or demote an admin back to employee.
- The super admin cannot be demoted, disabled, or deleted.
- A promoted admin keeps their employee profile, face, and attendance history. They can still be checked in at the desk.
- A disabled account cannot log in and is not expected at work.

## Architecture

Same shape as the app today: a Vue app, one FastAPI process, SQLite, and files on disk. Face recognition stays in that process. A second worker is not used, because it would load YOLO and ArcFace again.

```text
Browser
  Vue pages, cookie session
        |
        |  /api  and  /api/recognize
        v
FastAPI
  auth and roles
  employees, schedule, leave, holidays
  attendance day calculator
  YOLO (best.pt) + ArcFace
        |
        v
SQLite (data/app.db)          files (data/faces, data/attendance)
```

Three boundaries:

1. **Who is calling.** Login returns an HTTP-only cookie for 12 hours. The token stores the user id. Every request loads that user and checks `role` and `status`. The WebSocket does the same check before it accepts frames.
2. **Who was seen.** The desk sends a JPEG. Each face is judged in order: quality, then liveness, then a 1:N search of stored templates. Cosine distance is the score. Lower is closer. A match at **0.50 or lower** can get a short-lived match token bound to that admin and that employee. Confirming a punch consumes the token and stores the frame. The browser cannot invent a punch without a token the server just issued.
3. **What the day means.** Punches are not the record the HR screens read. Each employee has at most one workday row per local date. Check-in and check-out fill that row. Status, late minutes, and time worked are derived from the office schedule, approved leave, and holidays.

### Data

`users` — login. `username`, password hash, `role` (`super_admin`, `admin`, `employee`), `status` (`pending`, `active`, `disabled`).

`departments` — a name. An employee belongs to one department or none.

`employees` — the HR profile and the face identity. Unique link to `users` when they have an account. Employee code, name, position, `active` or `inactive`. Face samples hang off this row, as they do off people today.

`face_samples` — one photo and one ArcFace embedding per row. An employee holds up to five. The rows are searched one by one. They are not averaged into a single template.

`attendance_days` — one row per employee per `local_date`. Check-in time, distance, snapshot, and which user confirmed it. The same four fields for check-out. Computed `status`, `late_minutes`, `early_minutes`, `worked_minutes`. A note when a time was corrected by hand.

`leave_requests` — employee, type (`annual`, `sick`, `unpaid`), start date, end date, note, `pending` / `approved` / `rejected`, reviewer.

`holidays` — one row per office holiday date.

`office_settings` — one row: work start, work end, grace minutes, which weekdays are off. The super admin edits this in the app. Recognition settings (`MATCH_THRESHOLD`, weights, paths) stay in `backend/.env`.

Photos in `known_faces/` still import once when the employee table is empty. The filename becomes the name. A file that fails the enrollment face check is skipped. Those imports have no login until someone registers and an admin links them, or they stay as face-only employees the desk can punch.

### Face check

The same function judges an enrollment photo and a live box. Enrollment asks for a larger face. The desk also requires liveness, because an enrollment photo is a still.

| Check | Enrollment photo | Live frame |
| --- | --- | --- |
| Faces | Exactly one | Each box on its own |
| Size | Shorter side at least **120 px** | Shorter side at least **15%** of the frame height |
| Brightness | Mean of the crop from **40** to **220** | Same |
| Sharpness | Laplacian variance at least **80** | Same |
| Liveness | Not required | MiniFASNet must call the face real |
| Templates | Stored as its own embedding | Compared by cosine distance |

Search stays 1:N. Every sample of every matchable employee is compared, and the smallest distance wins. A new photo within **0.15** of a sample that employee already has is refused, so the five stay different. A sixth photo is refused until one is deleted.

A match is **0.50** or lower. A punch that happens on its own also needs **0.40** or lower, a passed quality check, and a gap of at least **0.05** to the next employee. A smaller gap stays on the confirm step.

A printed photo or a screen is labeled **Photo**, is not embedded, and cannot match. A live face that fails size, light, or sharpness is labeled **Move closer**. It gets no match token and does not start the three-frame streak. Liveness and identity stay separate scores.

Pose, landmarks, and occlusion are not part of this check.

### Request path for a punch

1. An admin opens Live and starts the camera.
2. Frames go to `/api/recognize`. Each box is checked for quality, then liveness, then matched against every stored template. **Photo** and **Move closer** are drawn and get no token. An unknown face is drawn and discarded.
3. The same known employee must be the largest face for three frames.
4. A clear match sends the match token and the current frame to `POST /api/attendance/punch`. A close match, including a clear distance whose next employee is within **0.05**, waits until someone presses **Check in** or **Check out**.
5. The API writes the punch, recomputes the day, and returns an undo token.
6. **Undo** calls `POST /api/attendance/undo` before that token expires.

**Not this person** hides a close match for eight seconds. The match token dies after 20 seconds.

## Features

### Register and login

Public pages are Register and Sign in.

Register asks for full name, username, and password. It creates a `pending` employee account and an employee row with no face. Duplicate usernames are rejected.

A pending user can sign in and sees only a waiting notice. They are not on the roster, and the camera cannot match them yet.

An admin or the super admin activates the account and adds a photo that passes the enrollment face check. Up to five different photos. After that, the desk can recognize them, and workdays count.

Sign in is the same form for every role. The home page depends on the role: employees land on My attendance, admins land on Live.

Anyone who is signed in can change their own password. The current password is required. The super admin can set a new password for any other account. An admin can set a new password for an employee login, not for another admin. The super admin's password only changes from the Password page.

### Accounts

Only the super admin sees Accounts.

The list shows every user, their role, and their status. From here the owner activates or disables an account, promotes an active employee to admin, and demotes an admin to employee. Pending accounts cannot be promoted.

### Employees

Admins maintain the roster: name, employee code, department, position, active or inactive, and face photos. A photo that fails the enrollment face check is rejected, and the screen shows why. Deleting an employee removes their photos and embeddings. Past workdays keep the stored name.

Inactive employees stay in history and are not expected on future days.

### Office schedule

The super admin sets one schedule for the office, for example 08:00–17:00 with 10 minutes of grace, and Saturday and Sunday off.

There is no per-person shift in this version. Everyone on the active roster follows that schedule.

### Live desk

A clear match punches itself. The distance must be at or below `AUTO_MATCH_THRESHOLD` (0.40 unless `MATCH_THRESHOLD` is stricter), the face must pass the live face check, the next employee must be at least **0.05** farther away, and the same person must be the largest face for three frames. The desk then shows who was punched and the time, with **Undo** for `UNDO_SECONDS` (8).

A close match, above that line and still at or below `MATCH_THRESHOLD`, keeps the confirm step. So does a would-be clear match when another employee is within **0.05**. **Check in** or **Check out**, then **Not this person** hides that employee for eight seconds.

Check-in opens today's workday. A second check-in the same day is refused.

Check-out closes it. Check-out before check-in is refused.

After a punch the same person is held until the cooldown (`PUNCH_COOLDOWN_SECONDS`, 45) has passed and they have left the frame, so standing at the desk does not check them out. Undo keeps that hold.

The stored snapshot is the frame from the moment of the punch, so the log can be audited later.

### Attendance

Office view, for admins: filter by employee, department, status, and date range. Each row shows the snapshot, name, check-in, check-out, status, and late minutes.

Employee view: the same fields for their own days only.

A day with no row is still shown. On a workday, an active employee with no punch, no approved leave, and no holiday is **absent**. The absence is calculated when the list is read. It is not typed in by hand.

Admins can correct a time when someone forgot a punch. The correction stores the new time, the reason, and who changed it. The face snapshot from a real punch is left as it was. A time that was never a face punch is marked manual.

An employee can ask for that correction instead of telling an admin outside the app. The request has a date, a check-in or a check-out (or both), and a reason. One pending request per employee per date. Admins approve or reject it. Approving writes the same manual correction. Pending and rejected requests do not change the workday.

The attendance list and the month summary each download as a CSV file for the current filters. Times are in `Asia/Phnom_Penh`.

### Day status

Computed in `APP_TIMEZONE` from the office schedule.

| Status | When |
| --- | --- |
| Present | Checked in by start + grace, and checked out at or after end |
| Late | Checked in after start + grace |
| Left early | Checked out before end |
| Incomplete | Checked in, not checked out |
| Absent | Workday over, active employee, no punches |
| On leave | Approved leave covers the date |
| Holiday | The date is an office holiday |

Late and left early can both apply. The row then shows both minute counts. Leave and holidays win over absence. A punch on a leave or holiday day is still stored, and the status stays on leave or holiday.

`late_minutes` is the time after the scheduled start, ignoring grace once the employee is already late. `worked_minutes` is check-out minus check-in.

### Leave

An employee submits a request with a type, a start date, an end date, and a note. Admins approve or reject it. Approved dates are on leave and are not absent. Rejected and pending dates are still workdays.

### Holidays

Admins add a date and a name. That date is a holiday for the whole office.

### Reports

Two views, not a payroll export:

- **Today** — who is in, late, still missing check-out, absent, or on leave.
- **Month** — per employee: days present, late count, absent count, leave days, total late minutes.

Both respect the department filter. The month summary downloads as CSV.

## Pages

| Page | Who |
| --- | --- |
| Register, Sign in | Public |
| Waiting | Pending employees |
| My attendance, Request leave | Employees |
| Password | Anyone signed in |
| Live | Admins, super admin |
| Employees, Attendance, Leave queue, Holidays, Today, Month | Admins, super admin |
| Accounts, Office hours | Super admin |

The header shows only the links that role can open.

## Scope

In this version:

- One super admin, promotable admins, and self-registered employees.
- One office schedule, departments, and up to five face templates per active employee.
- Check-in and check-out, with a snapshot. A clear match is automatic when the frame passes the face check and no other employee is nearly as close. A close match is confirmed.
- Derived status: present, late, left early, incomplete, absent, on leave, holiday.
- Leave requests and office holidays.
- Today and month summaries.
- A clear face match punches itself, with undo. A close match, or a near tie between two employees, still asks for confirmation.
- Manual correction of a punch time, with a reason, including a request an employee sends and an admin approves.
- CSV download of the attendance list and the month summary.
- Password change, and a reset by an admin or the super admin.
- SQLite and local files on one machine.

Not in this version:

- A second super admin, or admins who can promote other people.
- Payroll, salary, tax, contracts, or overtime pay.
- Per-person shifts, several offices, or several cameras.
- Punching from an employee's own phone. The desk camera is the only punch.
- Email or chat notifications.
- Saving unknown faces.
- Pose, landmark, or occlusion checks. Size, brightness, and blur are the quality gate.
- Averaging an employee's templates into one vector.
- Liveness on enrollment photos. Liveness runs on the live desk only.
- `detect.py`. That script writes `attendance_log.csv` and the website does not read it.
