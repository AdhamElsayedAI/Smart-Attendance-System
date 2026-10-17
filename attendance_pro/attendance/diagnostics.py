"""Read-only local device checks for the API diagnostics route."""
from __future__ import annotations

from .camera_service import CameraLease


def probe_camera(index: int, cv2_module=None) -> tuple[str, str]:
    """Return a concise status and always release a successfully created handle."""
    if cv2_module is None:
        try:
            import cv2 as cv2_module
        except ImportError as exc:
            return "Unavailable", f"OpenCV is unavailable: {exc}"
    capture = None
    lease = CameraLease(index)
    state, message = "Unavailable", f"Local camera {index} could not be opened. Check permissions and device selection."
    try:
        lease.acquire()
        capture = cv2_module.VideoCapture(index)
        if capture is not None and capture.isOpened():
            state, message = "Available", f"Local camera {index} opened successfully."
    except Exception as exc:  # OpenCV can raise cv2.error or a device-specific error.
        message = f"Local camera {index} could not be opened: {exc}"
    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception as exc:
                state, message = "Unavailable", f"Local camera {index} could not be released: {exc}"
        try:
            lease.release()
        except OSError as exc:
            state, message = "Unavailable", f"Local camera {index} lease could not be released: {exc}"
    return state, message
