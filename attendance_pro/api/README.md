# AttendanceOS local API

Run from `attendance_pro` with `python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log`. The OpenAPI explorer is at `http://127.0.0.1:8000/docs`. The adapter reuses `attendance/` services and has no login; keep it on loopback. Access logs are disabled because enrollment paths contain student IDs. Accepted browser origins are local Vite ports 5173 and 4173. Foreign `Origin` and cross-site fetch requests, including camera frame reads, and nonlocal `Host` headers are rejected.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | SQLite, CV modules, dlib/NumPy runtime check, model, enrolled count, camera and lease state |
| POST | `/api/diagnostics/camera` | Probe host camera and release device/lease; 409 during live capture |
| GET | `/api/overview` | Operational totals, featured exam, recent saved records, readiness |
| GET | `/api/students?search=` | Directory with ID, name, active and enrolled flags only |
| POST | `/api/students` | Register `{student_id, name}`; duplicate ID is 409 |
| POST | `/api/students/{id}/enrollment?filename=photo.jpg` | Raw JPG/PNG/BMP request body, appropriate `Content-Type`; 12 MB cap; returns status only |
| GET | `/api/exams` | Exams with assigned counts and `roster_complete` |
| POST | `/api/exams` | Create `{name, exam_date, start_time, end_time, description, student_ids}` |
| GET | `/api/exams/{id}/roster` | Exam, participant states, summary; `summary: null` for unknown historical roster |
| PUT | `/api/exams/{id}/roster` | Replace scheduled roster with `{student_ids}`; at least one active student |
| GET | `/api/exams/{id}/attendance` | Saved records for one exam |
| POST | `/api/exams/{id}/start` | Start eligible scheduled exam; at most one active exam |
| POST | `/api/exams/{id}/end` | Close camera and finish active exam |
| GET | `/api/analytics?exam_id=&exam_date=` | Filtered per-exam summaries and saved attendance rows |
| POST | `/api/session/camera/start` | Open host camera for the active exam |
| POST | `/api/session/camera/pause` | Release host camera; exam remains active |
| GET | `/api/session/status` | Current camera, face/identity/blink stage, saved outcome, roster progress |
| GET | `/api/session/frame` | Latest host JPEG with `no-store`, 404 before a frame is available |

Dates use ISO `YYYY-MM-DD`; times use 24-hour `HH:MM`. A scheduled exam may be started immediately for a supervised local demo even if the displayed timetable is earlier or later than the computer clock. Start/end times must form a valid interval. `recorded` is returned only after SQLite inserts the unique active-roster attendance row. The API never returns face embeddings or enrollment images. Kiosk clients call status/frame and receive no roster list.

Common errors: 422 invalid request, image, timetable, or roster; 409 duplicate ID, invalid session transition, camera unavailable/in use, or locked active roster; 404 unknown resource/no camera frame; 413 image too large; 415 unsupported upload content type; 503 native enrollment stack unavailable; 403 foreign write origin. FastAPI may return standard Pydantic validation details for malformed JSON.

Tests use temporary SQLite databases. The `create_app(db_path)` test factory also isolates the enrollment image folder next to that database. The background event pump processes camera events without any browser polling. The webcam and its advisory lease are released on pause, end, worker failure, or API shutdown.
