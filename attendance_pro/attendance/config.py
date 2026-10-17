"""Project paths and validated runtime settings."""
from dataclasses import dataclass
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    db_path: Path = BASE_DIR / "attendance_system.db"
    known_faces_dir: Path = BASE_DIR / "known_faces"
    landmarks_path: Path = BASE_DIR / "attendance" / "landmarks.dat"
    tolerance: float = 0.48
    model: str = "hog"
    blink_ear_threshold: float = 0.21
    blink_consec_frames: int = 2
    stable_frames: int = 3
    verification_seconds: int = 12
    camera_index: int = 0
    process_every_n_frames: int = 1


def _path(name: str, default: Path) -> Path:
    path = Path(os.getenv(name, str(default))).expanduser()
    return (BASE_DIR / path).resolve() if not path.is_absolute() else path.resolve()


def get_settings() -> Settings:
    s = Settings(
        db_path=_path("ATTENDANCE_DB", BASE_DIR / "attendance_system.db"),
        known_faces_dir=_path("KNOWN_FACES_DIR", BASE_DIR / "known_faces"),
        landmarks_path=_path("LANDMARKS_DAT", BASE_DIR / "attendance" / "landmarks.dat"),
        tolerance=float(os.getenv("FACE_TOLERANCE", "0.48")),
        model=os.getenv("FACE_MODEL", "hog"),
        blink_ear_threshold=float(os.getenv("BLINK_EAR_THRESHOLD", "0.21")),
        blink_consec_frames=int(os.getenv("BLINK_CONSEC_FRAMES", "2")),
        stable_frames=int(os.getenv("STABLE_FRAMES", "3")),
        verification_seconds=int(os.getenv("VERIFICATION_SECONDS", "12")),
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        process_every_n_frames=int(os.getenv("PROCESS_EVERY_N_FRAMES", "1")),
    )
    if not 0 < s.tolerance < 1 or not 0 < s.blink_ear_threshold < 1:
        raise ValueError("FACE_TOLERANCE and BLINK_EAR_THRESHOLD must be between 0 and 1")
    if min(s.blink_consec_frames, s.stable_frames, s.verification_seconds, s.process_every_n_frames) < 1:
        raise ValueError("Frame counts and verification duration must be positive")
    if s.model not in {"hog", "cnn"}:
        raise ValueError("FACE_MODEL must be hog or cnn")
    return s
