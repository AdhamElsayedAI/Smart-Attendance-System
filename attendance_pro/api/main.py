"""Loopback-only HTTP adapter. The database and camera engine remain authoritative."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date
from pathlib import Path
import importlib.util
import logging
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from attendance.camera_service import CameraLease
from attendance.config import get_settings
from attendance.db import Database
from attendance.diagnostics import probe_camera
from attendance.face_service import enroll_bytes
from attendance.migration import bootstrap
from .session import SessionManager


class StudentIn(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=150)


class ExamIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    exam_date: str
    start_time: str
    end_time: str
    description: str = Field(default="", max_length=1000)
    student_ids: list[str] = Field(min_length=1)


class RosterIn(BaseModel):
    student_ids: list[str] = Field(min_length=1)


def create_app(db_path: str | Path | None = None) -> FastAPI:
    settings = get_settings()
    if db_path is not None:
        settings = replace(settings, db_path=Path(db_path).resolve(),
                           known_faces_dir=Path(db_path).resolve().with_suffix(".faces"))
    db = Database(db_path or settings.db_path)
    session = SessionManager(db, settings)
    camera_probe_state = {"state": "Not tested", "message": "Run the local camera probe to check the device."}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logging.getLogger("uvicorn.access").disabled = True  # Request paths can contain student IDs.
        bootstrap(db)
        try:
            yield
        finally:
            session.stop_camera()

    app = FastAPI(title="AttendanceOS local API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173",
                                                    "http://127.0.0.1:4173", "http://localhost:4173"],
                       allow_credentials=False, allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
    app.state.db = db
    app.state.session = session

    @app.middleware("http")
    async def protect_local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        allowed_origins = {
            "http://127.0.0.1:5173", "http://localhost:5173",
            "http://127.0.0.1:4173", "http://localhost:4173",
        }
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin not in allowed_origins):
            return Response("Local origin required", status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    def health():
        try:
            with db.connect() as conn:
                database = conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            database = False
        try:
            import dlib
            import numpy as np
            dlib.get_frontal_face_detector()(np.zeros((10, 10, 3), dtype=np.uint8))
            native = {"state": "compatible", "message": "dlib accepts NumPy RGB frames"}
        except Exception as exc:
            native = {"state": "unavailable", "message": str(exc)}
        try:
            enrolled = sum(bool(s["active"] and s["enrolled"]) for s in db.students()) if database else 0
        except sqlite3.Error:
            enrolled = 0
        if session.camera is not None:
            lease_state = "Held by this API"
        else:
            lease = CameraLease(settings.camera_index)
            try:
                lease.acquire()
                lease_state = "Free"
            except RuntimeError:
                lease_state = "Held by another process"
            finally:
                lease.release()
        return {"database": "healthy" if database else "unavailable",
                "face_module": bool(importlib.util.find_spec("face_recognition")),
                "opencv": bool(importlib.util.find_spec("cv2")),
                "dlib_numpy": native,
                "landmark_model": settings.landmarks_path.is_file(),
                "enrolled": enrolled,
                "camera_lease": lease_state,
                "camera": {"state": "Active", "message": "Host camera session is running."}
                          if session.camera is not None else camera_probe_state}

    @app.get("/api/overview")
    def overview():
        exams, students, records = db.exams(), db.students(), db.records()
        readiness = health()
        active = next((e for e in exams if e["status"] == "active"), None)
        upcoming = sorted((e for e in exams if e["status"] == "scheduled" and
                           e["exam_date"] >= date.today().isoformat()),
                          key=lambda e: (e["exam_date"], e["start_time"]))
        featured = active or (upcoming[0] if upcoming else None)
        distribution = [{"exam_id": e["id"], "name": e["name"], "date": e["exam_date"],
                         "count": sum(r["exam_id"] == e["id"] for r in records)} for e in exams]
        return {"active": active, "featured": featured, "metrics": {
            "students": sum(bool(s["active"]) for s in students),
            "enrolled": sum(bool(s["active"] and s["enrolled"]) for s in students),
            "exams": len(exams), "upcoming": len(upcoming), "events": len(records)},
            "recent": records[:6], "distribution": distribution,
            "readiness": readiness,
            "attention": {"unenrolled": sum(bool(s["active"] and not s["enrolled"]) for s in students),
                          "landmark_missing": not settings.landmarks_path.is_file()},
            "featured_summary": db.exam_summary(featured["id"]) if featured and featured["roster_complete"] else None}

    @app.get("/api/exams")
    def exams():
        return db.exams()

    @app.get("/api/students")
    def students(search: str = ""):
        return db.students(search[:150])

    @app.post("/api/students", status_code=201)
    def create_student(payload: StudentIn):
        try:
            db.add_student(payload.student_id, payload.name)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Student ID is already registered") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return next(row for row in db.students() if row["student_id"] == payload.student_id.strip())

    @app.post("/api/students/{student_id}/enrollment")
    async def enroll(student_id: str, request: Request, filename: str = "photo.jpg"):
        if request.headers.get("content-type", "").split(";")[0] not in {"image/jpeg", "image/png", "image/bmp"}:
            raise HTTPException(415, "Upload a JPG, PNG, or BMP image")
        if not any(row["student_id"] == student_id and row["active"] for row in db.students()):
            raise HTTPException(404, "Active student not found")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 12 * 1024 * 1024:
                raise HTTPException(413, "Image exceeds the 12 MB limit")
        try:
            await run_in_threadpool(enroll_bytes, db, student_id, filename, bytes(data), settings)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "This face or image is already enrolled") from exc
        except (ImportError, RuntimeError) as exc:
            raise HTTPException(503, f"Face enrollment is unavailable: {exc}") from exc
        return {"student_id": student_id, "enrolled": True}

    @app.post("/api/exams", status_code=201)
    def create_exam(payload: ExamIn):
        try:
            exam_id = db.create_exam(payload.name, payload.exam_date, payload.start_time,
                                     payload.end_time, payload.student_ids, payload.description)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"exam": db.exam(exam_id)}

    @app.put("/api/exams/{exam_id}/roster")
    def set_roster(exam_id: int, payload: RosterIn):
        if db.exam(exam_id) is None:
            raise HTTPException(404, "Exam not found")
        try:
            db.set_roster(exam_id, payload.student_ids)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"exam": db.exam(exam_id), "participants": db.roster(exam_id)}

    @app.get("/api/analytics")
    def analytics(exam_id: int | None = None, exam_date: str | None = None):
        if exam_date:
            try:
                date.fromisoformat(exam_date)
            except ValueError as exc:
                raise HTTPException(422, "Use an ISO exam date") from exc
        all_exams = db.exams()
        if exam_id is not None and not any(row["id"] == exam_id for row in all_exams):
            raise HTTPException(404, "Exam not found")
        filtered = [row for row in all_exams if (exam_id is None or row["id"] == exam_id)
                    and (exam_date is None or row["exam_date"] == exam_date)]
        summaries = [{"exam": row, "summary": db.exam_summary(row["id"]) if row["roster_complete"] else None,
                      "records": len(db.records(row["id"]))} for row in filtered]
        records = [record for record in db.records(exam_id) if any(row["id"] == record["exam_id"] for row in filtered)]
        return {"exams": summaries, "records": records}

    @app.get("/api/exams/{exam_id}/roster")
    def roster(exam_id: int):
        exam = db.exam(exam_id)
        if exam is None:
            raise HTTPException(404, "Exam not found")
        return {"exam": exam, "summary": db.exam_summary(exam_id) if exam["roster_complete"] else None,
                "participants": db.roster(exam_id) if exam["roster_complete"] else []}

    @app.get("/api/exams/{exam_id}/attendance")
    def attendance(exam_id: int):
        if db.exam(exam_id) is None:
            raise HTTPException(404, "Exam not found")
        return db.records(exam_id)

    @app.post("/api/exams/{exam_id}/start")
    def start_exam(exam_id: int):
        try:
            db.set_exam_status(exam_id, "active")
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"exam": db.exam(exam_id)}

    @app.post("/api/exams/{exam_id}/end")
    def end_exam(exam_id: int):
        exam = db.exam(exam_id)
        if exam is None:
            raise HTTPException(404, "Exam not found")
        if exam["status"] != "active":
            raise HTTPException(409, "Exam session is not active")
        try:
            session.stop_camera()
            db.set_exam_status(exam_id, "ended")
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"exam": db.exam(exam_id)}

    @app.post("/api/session/camera/start")
    def start_camera():
        try:
            session.start_camera()
        except (ValueError, RuntimeError, OSError, ImportError, FileNotFoundError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"camera": "connecting"}

    @app.post("/api/session/camera/pause")
    def pause_camera():
        try:
            session.stop_camera()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"camera": "paused"}

    @app.get("/api/session/status")
    def session_status():
        return session.status()

    @app.get("/api/session/frame")
    def frame():
        jpeg = session.frame()
        if jpeg is None:
            raise HTTPException(404, "No camera frame available")
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/api/diagnostics/camera")
    def camera_probe():
        if session.camera is not None:
            raise HTTPException(409, "Pause the live camera before probing")
        state, message = probe_camera(settings.camera_index)
        camera_probe_state.update(state=state, message=message)
        return camera_probe_state

    return app


app = create_app()
