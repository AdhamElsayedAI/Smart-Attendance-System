"""One-time, non-destructive import of the two legacy attendance databases."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import logging
import sqlite3

from .config import BASE_DIR
from .db import Database

LOG = logging.getLogger(__name__)
LEGACY_FILES = (BASE_DIR / "attendance.db", BASE_DIR / "attendance" / "attendance.db")


def legacy_student_id(name: str) -> str:
    return "LEG-" + sha256(name.strip().casefold().encode()).hexdigest()[:12].upper()


def bootstrap(db: Database) -> None:
    """Create a clean database; import old files only on first default-path startup.

    Original databases and enrollment images are never modified. Repeated calls are safe.
    """
    existed = db.path.exists()
    if existed:
        with closing(sqlite3.connect(db.path)) as existing:
            columns = {row[1] for row in existing.execute("PRAGMA table_info(attendance)")}
            if "student_name" in columns and "student_id" not in columns:
                raise ValueError("ATTENDANCE_DB points to an old database. Use a new path for the V1 database; originals are imported automatically at the default path.")
    db.init()
    if db.path != (BASE_DIR / "attendance_system.db").resolve():
        return
    with db.connect() as target:
        target.execute("CREATE TABLE IF NOT EXISTS migration_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = target.execute("SELECT value FROM migration_state WHERE key='legacy_import'").fetchone()
        if row is None:
            target.execute("INSERT INTO migration_state(key,value) VALUES('legacy_import',?)",
                           ("skipped_existing" if existed else "pending",))
            state = "skipped_existing" if existed else "pending"
        else:
            state = row[0]
    if state != "pending":
        return
    with db.connect() as target:
        for source_path in LEGACY_FILES:
            if not source_path.is_file():
                continue
            try:
                uri = source_path.resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(uri, uri=True)) as source:
                    exams = source.execute("SELECT id,name,exam_date,start_time,end_time,created_at FROM exams").fetchall()
                    records = source.execute("SELECT exam_id,student_name,timestamp FROM attendance").fetchall()
            except sqlite3.DatabaseError as exc:
                LOG.error("Legacy database could not be imported: %s: %s", source_path, exc)
                raise
            for folder in (BASE_DIR / "known_faces").iterdir() if (BASE_DIR / "known_faces").is_dir() else ():
                if folder.is_dir():
                    sid = legacy_student_id(folder.name)
                    target.execute("INSERT OR IGNORE INTO students(student_id,name,created_at) VALUES(?,?,?)",
                                   (sid, folder.name, db.now()))
            for _, name, _ in records:
                sid = legacy_student_id(name)
                target.execute("INSERT OR IGNORE INTO students(student_id,name,created_at) VALUES(?,?,?)",
                               (sid, name, db.now()))
            mapping = {}
            for legacy_id, name, day, start, end, created in exams:
                if not start or not end or start >= end:
                    LOG.warning("Skipping invalid legacy exam %s in %s", legacy_id, source_path)
                    continue
                cur = target.execute("""INSERT INTO exams(name,exam_date,start_time,end_time,status,created_at,roster_complete)
                    VALUES(?,?,?,?,'ended',?,0)""", (name or "Untitled legacy exam", day, start, end, created or db.now()))
                mapping[legacy_id] = cur.lastrowid
            for legacy_id, name, timestamp in records:
                if legacy_id not in mapping:
                    continue
                sid, exam_id = legacy_student_id(name), mapping[legacy_id]
                target.execute("INSERT OR IGNORE INTO exam_participants(exam_id,student_id) VALUES(?,?)", (exam_id, sid))
                target.execute("""INSERT OR IGNORE INTO attendance(exam_id,student_id,timestamp,verification_method)
                    VALUES(?,?,?,'legacy_unverified')""", (exam_id, sid, timestamp))
            LOG.info("Imported %d exams and %d attendance rows from %s", len(exams), len(records), source_path)
        target.execute("UPDATE migration_state SET value='complete' WHERE key='legacy_import'")
