"""SQLite persistence with exam-scoped enrollment and attendance."""
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
import re
import sqlite3
from typing import Iterator

from .config import get_settings


class Database:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or get_settings().db_path).resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS face_enrollments (
                    student_id TEXT PRIMARY KEY REFERENCES students(student_id),
                    image_path TEXT NOT NULL, embedding BLOB NOT NULL,
                    image_sha256 TEXT NOT NULL UNIQUE, enrolled_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, exam_date TEXT NOT NULL,
                    start_time TEXT NOT NULL, end_time TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'scheduled'
                        CHECK(status IN ('scheduled','active','ended')),
                    created_at TEXT NOT NULL, roster_complete INTEGER NOT NULL DEFAULT 1,
                    CHECK(start_time < end_time));
                CREATE TABLE IF NOT EXISTS exam_participants (
                    exam_id INTEGER NOT NULL REFERENCES exams(id),
                    student_id TEXT NOT NULL REFERENCES students(student_id),
                    PRIMARY KEY(exam_id, student_id));
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                    verification_method TEXT NOT NULL DEFAULT 'blink',
                    FOREIGN KEY(exam_id,student_id)
                        REFERENCES exam_participants(exam_id,student_id),
                    UNIQUE(exam_id,student_id));
                CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance(timestamp);
            """)
            if "description" not in {row[1] for row in conn.execute("PRAGMA table_info(exams)")}:
                conn.execute("ALTER TABLE exams ADD COLUMN description TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def add_student(self, student_id: str, name: str) -> None:
        student_id, name = student_id.strip(), name.strip()
        if not student_id or not name or len(student_id) > 64 or len(name) > 150:
            raise ValueError("Student ID and name are required (maximum 64 and 150 characters)")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", student_id) is None:
            raise ValueError("Student ID may contain letters, numbers, dots, dashes, and underscores")
        with self.connect() as conn:
            conn.execute("INSERT INTO students(student_id,name,created_at) VALUES(?,?,?)",
                         (student_id, name, self.now()))

    def update_student(self, student_id: str, name: str, active: bool = True) -> None:
        if not name.strip():
            raise ValueError("Student name is required")
        with self.connect() as conn:
            if not conn.execute("UPDATE students SET name=?,active=? WHERE student_id=?",
                                (name.strip(), int(active), student_id)).rowcount:
                raise ValueError("Student not found")

    def students(self, search: str = "") -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("""SELECT s.student_id,s.name,s.active,
                (f.student_id IS NOT NULL) AS enrolled FROM students s
                LEFT JOIN face_enrollments f USING(student_id)
                WHERE s.student_id LIKE ? OR s.name LIKE ? ORDER BY s.name""",
                (f"%{search}%", f"%{search}%"))]

    def save_enrollment(self, student_id: str, image_path: str, embedding: bytes, sha256: str) -> None:
        with self.connect() as conn:
            conn.execute("""INSERT INTO face_enrollments(student_id,image_path,embedding,image_sha256,enrolled_at)
                VALUES(?,?,?,?,?) ON CONFLICT(student_id) DO UPDATE SET
                image_path=excluded.image_path,embedding=excluded.embedding,
                image_sha256=excluded.image_sha256,enrolled_at=excluded.enrolled_at""",
                (student_id, image_path, embedding, sha256, self.now()))

    def enrollments(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("""SELECT f.student_id,s.name,f.embedding,f.image_path
                FROM face_enrollments f JOIN students s USING(student_id) WHERE s.active=1""")]

    def create_exam(self, name: str, exam_date: str, start_time: str, end_time: str,
                    student_ids: list[str], description: str = "") -> int:
        try:
            parsed_date = date.fromisoformat(exam_date)
            parsed_start = time.fromisoformat(start_time)
            parsed_end = time.fromisoformat(end_time)
        except ValueError as exc:
            raise ValueError("Use ISO exam date and valid start/end times") from exc
        if (not name.strip() or len(name.strip()) > 150 or parsed_start >= parsed_end or
                not student_ids or len(description.strip()) > 1000 or len(set(student_ids)) != len(student_ids)):
            raise ValueError("Provide an exam name, valid time range, and participants")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = {r[0] for r in conn.execute("SELECT student_id FROM students WHERE active=1")}
            if not set(student_ids) <= active:
                raise ValueError("All participants must be active registered students")
            cur = conn.execute("INSERT INTO exams(name,exam_date,start_time,end_time,description,created_at) VALUES(?,?,?,?,?,?)",
                               (name.strip(), parsed_date.isoformat(), parsed_start.strftime("%H:%M"),
                                parsed_end.strftime("%H:%M"), description.strip(), self.now()))
            conn.executemany("INSERT INTO exam_participants(exam_id,student_id) VALUES(?,?)",
                             [(cur.lastrowid, sid) for sid in set(student_ids)])
            return int(cur.lastrowid)

    def set_roster(self, exam_id: int, student_ids: list[str]) -> None:
        if not student_ids or len(set(student_ids)) != len(student_ids):
            raise ValueError("Select at least one distinct participant")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exam = conn.execute("SELECT status FROM exams WHERE id=?", (exam_id,)).fetchone()
            if not exam or exam[0] != "scheduled":
                raise ValueError("Only a scheduled exam roster can be changed")
            active = {r[0] for r in conn.execute("SELECT student_id FROM students WHERE active=1")}
            if not set(student_ids) <= active:
                raise ValueError("All participants must be active registered students")
            conn.execute("DELETE FROM exam_participants WHERE exam_id=?", (exam_id,))
            conn.executemany("INSERT INTO exam_participants(exam_id,student_id) VALUES(?,?)",
                             [(exam_id, sid) for sid in student_ids])
            conn.execute("UPDATE exams SET roster_complete=1 WHERE id=?", (exam_id,))

    def exams(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("""SELECT e.*,COUNT(p.student_id) AS assigned
                FROM exams e LEFT JOIN exam_participants p ON p.exam_id=e.id
                GROUP BY e.id ORDER BY e.exam_date DESC,e.start_time DESC,e.id DESC""")]

    def exam(self, exam_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
            return dict(row) if row else None

    def set_exam_status(self, exam_id: int, status: str) -> None:
        if status not in {"active", "ended"}:
            raise ValueError("Invalid session status")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exam = conn.execute("SELECT status FROM exams WHERE id=?", (exam_id,)).fetchone()
            if not exam or (status == "active" and exam[0] != "scheduled") or (status == "ended" and exam[0] != "active"):
                raise ValueError("Exam cannot make this status transition")
            if status == "active" and conn.execute("SELECT 1 FROM exams WHERE status='active' AND id<>?", (exam_id,)).fetchone():
                raise ValueError("End the current active exam before starting another")
            conn.execute("UPDATE exams SET status=? WHERE id=?", (status, exam_id))

    def record_attendance(self, exam_id: int, student_id: str, method: str = "blink") -> bool:
        if method != "blink":
            raise ValueError("Only validated blink attendance may be recorded")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exam = conn.execute("SELECT status FROM exams WHERE id=?", (exam_id,)).fetchone()
            if not exam or exam[0] != "active":
                raise ValueError("Exam session is not active")
            cur = conn.execute("""INSERT OR IGNORE INTO attendance(exam_id,student_id,timestamp,verification_method)
                SELECT ?,p.student_id,?,? FROM exam_participants p
                JOIN students s ON s.student_id=p.student_id
                WHERE p.exam_id=? AND p.student_id=? AND s.active=1""",
                (exam_id, self.now(), method, exam_id, student_id))
            return cur.rowcount == 1

    def records(self, exam_id: int | None = None, student_search: str = "", date: str | None = None) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("""SELECT a.exam_id,e.name AS exam,s.student_id,
                s.name AS student,a.timestamp,a.verification_method FROM attendance a
                JOIN exams e ON e.id=a.exam_id JOIN students s ON s.student_id=a.student_id
                WHERE (? IS NULL OR a.exam_id=?) AND (? IS NULL OR substr(a.timestamp,1,10)=?)
                AND (s.name LIKE ? OR s.student_id LIKE ?) ORDER BY a.timestamp DESC""",
                (exam_id, exam_id, date, date, f"%{student_search}%", f"%{student_search}%"))]

    def exam_summary(self, exam_id: int) -> dict:
        with self.connect() as conn:
            row = conn.execute("""SELECT COUNT(*),SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END)
                FROM exam_participants p LEFT JOIN attendance a
                ON a.exam_id=p.exam_id AND a.student_id=p.student_id WHERE p.exam_id=?""", (exam_id,)).fetchone()
            assigned, present = row[0], row[1] or 0
            return {"assigned": assigned, "present": present, "absent": assigned-present,
                    "rate": round(100*present/assigned, 1) if assigned else None}

    def attendance_reason(self, exam_id: int, student_id: str) -> str:
        with self.connect() as conn:
            if conn.execute("SELECT 1 FROM attendance WHERE exam_id=? AND student_id=?",
                            (exam_id, student_id)).fetchone():
                return "Attendance was already recorded for this student."
            if not conn.execute("""SELECT 1 FROM exam_participants p JOIN students s
                ON p.student_id=s.student_id WHERE p.exam_id=? AND p.student_id=? AND s.active=1""",
                (exam_id, student_id)).fetchone():
                return "Recognized student is not assigned to this examination. Ask the supervisor for help."
            return "Attendance was not recorded. Ask the supervisor to retry."

    def roster(self, exam_id: int) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("""SELECT s.student_id,s.name,
                CASE WHEN a.id IS NULL THEN 'Absent' ELSE 'Present' END AS status,a.timestamp
                FROM exam_participants p JOIN students s ON s.student_id=p.student_id
                LEFT JOIN attendance a ON a.exam_id=p.exam_id AND a.student_id=p.student_id
                WHERE p.exam_id=? ORDER BY s.name""", (exam_id,))]
