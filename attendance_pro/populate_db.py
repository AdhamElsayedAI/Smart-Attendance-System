"""Explicit, idempotent import of local legacy enrollment photos."""
import logging

from attendance.config import get_settings
from attendance.db import Database
from attendance.face_service import IMAGE_EXTENSIONS, enroll_bytes
from attendance.migration import bootstrap, legacy_student_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    db = Database(settings.db_path)
    bootstrap(db)
    if not settings.known_faces_dir.is_dir():
        LOG.error("No face image directory: %s", settings.known_faces_dir)
        return 1
    imported, failed = 0, 0
    for folder in sorted(settings.known_faces_dir.iterdir()):
        if not folder.is_dir() or (len(folder.name) == 20 and all(c in "0123456789abcdef" for c in folder.name)):
            continue
        student_id = legacy_student_id(folder.name)
        if not any(s["student_id"] == student_id for s in db.students()):
            db.add_student(student_id, folder.name)
        if any(e["student_id"] == student_id for e in db.enrollments()):
            LOG.info("Already enrolled: %s", folder.name)
            continue
        images = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
        if not images:
            LOG.warning("No supported images for %s", folder.name)
            failed += 1
            continue
        for image in images:
            try:
                enroll_bytes(db, student_id, image.name, image.read_bytes(), settings)
                LOG.info("Enrolled %s from %s", folder.name, image.name)
                imported += 1
                break
            except (ValueError, RuntimeError, OSError, ImportError) as exc:
                LOG.warning("Could not use %s for %s: %s", image.name, folder.name, exc)
        else:
            failed += 1
    LOG.info("Imported %d, failed %d", imported, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
