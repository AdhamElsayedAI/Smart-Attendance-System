"""Stoppable local-camera worker. No database calls in the worker."""
from collections import deque
from threading import Event, Lock, Thread
import logging
import os
from pathlib import Path
from tempfile import gettempdir

from .liveness_service import BlinkChallenge

LOG = logging.getLogger(__name__)


class CameraLease:
    """Exclusive advisory lock shared by API and diagnostics processes."""

    def __init__(self, index: int):
        self.path = Path(gettempdir()) / f"attendanceos-camera-{index}.lock"
        self.handle = None
        self._lock = Lock()

    def acquire(self) -> None:
        handle = open(self.path, "a+b")
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RuntimeError("Local camera is in use by another AttendanceOS process") from exc
        self.handle = handle

    def release(self) -> None:
        with self._lock:
            handle, self.handle = self.handle, None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


class LocalCameraSession:
    def __init__(self, recognizer, settings):
        import cv2
        self.recognizer = recognizer
        self.settings = settings
        self.lease = CameraLease(settings.camera_index)
        self.lease.acquire()
        try:
            self.capture = cv2.VideoCapture(settings.camera_index)
            if not self.capture.isOpened():
                raise RuntimeError(f"Local camera {settings.camera_index} is unavailable")
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.challenge = BlinkChallenge(settings.blink_ear_threshold, settings.blink_consec_frames,
                                            settings.stable_frames, settings.verification_seconds)
            self.stop_event = Event()
            self.lock = Lock()
            self.frame_jpeg = None
            self.feedback = "Camera connecting"
            self.identity = None
            self.identity_id = None
            self.stage = "Waiting"
            self.face_count = 0
            self.stable_frames = 0
            self.error = None
            self.events = deque(maxlen=16)
            self.verification_emitted = False
            self.thread = Thread(target=self._run, name="attendance-local-camera", daemon=True)
            self.thread.start()
        except Exception:
            if hasattr(self, "capture") and self.capture is not None:
                self.capture.release()
            self.lease.release()
            raise

    def _run(self) -> None:
        import cv2
        frame_number = 0
        try:
            while not self.stop_event.is_set():
                ok, frame = self.capture.read()
                if not ok or frame is None:
                    raise RuntimeError("Camera frame could not be read")
                frame_number += 1
                if frame_number % self.settings.process_every_n_frames == 0:
                    result = self.recognizer.recognize(frame)
                    self._update_recognition(result)
                ok, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    with self.lock:
                        self.frame_jpeg = image.tobytes()
        except Exception as exc:
            LOG.exception("Camera processing stopped")
            with self.lock:
                self.error = str(exc)
                self.feedback = "Camera disconnected"
        finally:
            self.capture.release()
            self.lease.release()
            self.stop_event.set()

    def _update_recognition(self, result) -> None:
        challenge = self.challenge.observe(result["identity"], result["ear"], result["face_count"])
        if result["face_count"] != 1:
            stage = "Waiting"
        elif result["identity"] is None:
            stage = "Face detected"
        elif challenge.verified:
            stage = "Verified"
        elif challenge.stable_frames < self.settings.stable_frames:
            stage = "Identity matched"
        else:
            stage = "Blink required"
        with self.lock:
            self.feedback = challenge.message
            self.identity = result["name"]
            self.identity_id = result["identity"]
            self.face_count = result["face_count"]
            self.stable_frames = challenge.stable_frames
            self.stage = stage
            if challenge.verified and not self.verification_emitted:
                self.events.append((result["identity"], result["name"]))
                self.verification_emitted = True
            elif not challenge.verified:
                self.verification_emitted = False

    def snapshot(self):
        with self.lock:
            events = list(self.events)
            self.events.clear()
            return {"frame": self.frame_jpeg, "feedback": self.feedback,
                    "identity": self.identity, "identity_id": self.identity_id,
                    "face_count": self.face_count, "stable_frames": self.stable_frames,
                    "stage": self.stage, "error": self.error, "events": events}

    def frame(self) -> bytes | None:
        """Read the current JPEG without consuming verification events."""
        with self.lock:
            return self.frame_jpeg

    def close(self) -> bool:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=3)
        if not self.thread.is_alive():
            self.capture.release()
            self.lease.release()
            return True
        return False

    def __del__(self):
        if hasattr(self, "thread") and hasattr(self, "stop_event"):
            self.close()
        elif hasattr(self, "lease"):
            self.lease.release()
