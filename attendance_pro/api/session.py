"""Single-owner local camera session; verified events are saved independently of UI polls."""
from __future__ import annotations

from threading import Event, RLock, Thread
from time import monotonic

from attendance.camera_service import LocalCameraSession
from attendance.db import Database
from attendance.face_service import FaceRecognizer
from attendance.config import Settings


class SessionManager:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings
        self.camera: LocalCameraSession | None = None
        self.exam_id: int | None = None
        self.lock = RLock()
        self.pump_stop = Event()
        self.pump: Thread | None = None
        self.latest: dict | None = None
        self.last_error: str | None = None
        self.last_outcome: dict | None = None
        self.last_outcome_id: str | None = None
        self.last_outcome_at = 0.0

    def start_camera(self) -> None:
        with self.lock:
            if self.camera is not None:
                raise ValueError("Camera is already running")
            active = next((e for e in self.db.exams() if e["status"] == "active"), None)
            if active is None:
                raise ValueError("Start an exam session first")
            camera = LocalCameraSession(FaceRecognizer(self.db, self.settings), self.settings)
            self.camera = camera
            self.exam_id = active["id"]
            self.latest = None
            self.last_error = None
            self.last_outcome = None
            self.pump_stop = Event()
            self.pump = Thread(target=self._pump, args=(camera, self.pump_stop),
                               name="attendance-api-events", daemon=True)
            self.pump.start()

    def _process_once(self, camera: LocalCameraSession) -> None:
        snapshot = camera.snapshot()
        with self.lock:
            if self.camera is not camera:
                return
            self.latest = snapshot
            for student_id, name in snapshot["events"]:
                try:
                    if self.exam_id is None:
                        raise ValueError("Camera session has no bound examination")
                    inserted = self.db.record_attendance(self.exam_id, student_id)
                    self.last_outcome = {"kind": "recorded" if inserted else "rejected",
                                         "message": f"Attendance recorded for {name}." if inserted else
                                         self.db.attendance_reason(self.exam_id, student_id)}
                except Exception as exc:
                    self.last_outcome = {"kind": "error", "message": f"Attendance could not be saved: {exc}"}
                self.last_outcome_id, self.last_outcome_at = student_id, monotonic()

    def _pump(self, camera: LocalCameraSession, stop: Event) -> None:
        try:
            while not stop.wait(.12):
                self._process_once(camera)
                if camera.stop_event.is_set() or not camera.thread.is_alive():
                    self._process_once(camera)
                    camera.close()
                    with self.lock:
                        if self.camera is camera:
                            self.last_error = (self.latest or {}).get("error") or "Camera worker stopped"
                            self.camera = None
                    return
        except Exception as exc:
            camera.close()
            with self.lock:
                if self.camera is camera:
                    self.last_error = f"Camera session stopped: {exc}"
                    self.camera = None

    def stop_camera(self) -> None:
        with self.lock:
            camera, pump = self.camera, self.pump
            self.pump_stop.set()
        if camera is not None:
            if not camera.close():
                raise RuntimeError("Camera worker is still stopping; try again")
            self._process_once(camera)  # Do not lose a final verified event while pausing.
        if pump is not None and pump.is_alive():
            pump.join(timeout=3)
        with self.lock:
            if self.camera is camera:
                self.camera = None
                self.exam_id = None
            self.pump = None
            self.latest = None
            self.last_error = None

    def frame(self) -> bytes | None:
        with self.lock:
            return self.camera.frame() if self.camera is not None else None

    def status(self) -> dict:
        with self.lock:
            active = next((e for e in self.db.exams() if e["status"] == "active"), None)
            progress = self.db.exam_summary(active["id"]) if active and active["roster_complete"] else None
            if self.camera is None:
                return {"exam": active, "camera": "disconnected" if self.last_error else "paused",
                        "stage": "Waiting", "identity": None,
                        "feedback": "Check the device and resume." if self.last_error else "Start the host camera when ready.",
                        "face_count": 0, "outcome": None, "progress": progress, "error": self.last_error}
            snapshot = self.latest or {"stage": "Waiting", "identity": None, "identity_id": None,
                                       "feedback": "Camera connecting", "face_count": 0, "error": None}
            current_id = snapshot["identity_id"]
            outcome = self.last_outcome if (monotonic() - self.last_outcome_at < 5 and
                         (current_id == self.last_outcome_id or
                          snapshot["face_count"] == 0)) else None
            stage = "Recorded" if outcome and outcome["kind"] == "recorded" else snapshot["stage"]
            return {"exam": active, "camera": "connected" if self.camera.thread.is_alive() else "disconnected",
                    "stage": stage, "identity": snapshot["identity"], "feedback": snapshot["feedback"],
                    "face_count": snapshot["face_count"], "outcome": outcome,
                    "progress": progress, "error": snapshot["error"]}
