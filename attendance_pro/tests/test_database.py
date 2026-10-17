import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from attendance.db import Database
from attendance import migration


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database(Path(self.temp.name) / "test.db")
        self.db.init()

    def test_creation_assignment_attendance_and_persistence(self):
        self.db.init()
        self.db.add_student("S-001", "Alice")
        self.db.add_student("S-002", "Bob")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_student("S-001", "Duplicate")
        exam = self.db.create_exam("Calculus", "2026-10-16", "09:00", "10:00", ["S-001", "S-002"])
        with self.assertRaises(ValueError):
            self.db.record_attendance(exam, "S-001")
        self.db.set_exam_status(exam, "active")
        self.assertTrue(self.db.record_attendance(exam, "S-001"))
        self.assertFalse(self.db.record_attendance(exam, "S-001"))
        self.assertFalse(self.db.record_attendance(exam, "unknown"))
        self.assertEqual(self.db.exam_summary(exam), {"assigned": 2, "present": 1, "absent": 1, "rate": 50.0})
        self.assertEqual(len(Database(self.db.path).records(exam)), 1)
        self.assertEqual(self.db.roster(exam)[0]["status"], "Present")
        self.db.set_exam_status(exam, "ended")
        with self.assertRaises(ValueError):
            self.db.record_attendance(exam, "S-002")

    def test_exam_filters_and_invalid_transitions(self):
        self.db.add_student("A", "Alice")
        first = self.db.create_exam("One", "2026-10-16", "09:00", "10:00", ["A"])
        second = self.db.create_exam("Two", "2026-10-17", "09:00", "10:00", ["A"])
        self.db.set_exam_status(first, "active")
        with self.assertRaises(ValueError):
            self.db.set_exam_status(second, "active")
        self.db.record_attendance(first, "A")
        self.assertEqual(len(self.db.records(first)), 1)
        self.assertEqual(len(self.db.records(second)), 0)
        self.assertEqual(len(self.db.records(date="1900-01-01")), 0)
        self.assertEqual(len(self.db.records(student_search="lice")), 1)

    def test_legacy_import_preserves_sources_and_marks_incomplete_roster(self):
        root = Path(self.temp.name) / "legacy"
        (root / "attendance").mkdir(parents=True)
        (root / "known_faces" / "Alice").mkdir(parents=True)
        source = root / "attendance.db"
        with closing(sqlite3.connect(source)) as conn:
            conn.executescript("""CREATE TABLE exams(id INTEGER PRIMARY KEY,name TEXT,exam_date TEXT,
                start_time TEXT,end_time TEXT,created_at TEXT);
                CREATE TABLE attendance(id INTEGER PRIMARY KEY,exam_id INTEGER,student_name TEXT,timestamp TEXT);
                INSERT INTO exams VALUES(1,'Exam','2026-01-01','09:00','10:00','2026-01-01T09:00');
                INSERT INTO attendance VALUES(1,1,'Alice','2026-01-01T09:02');""")
            conn.commit()
        before = source.read_bytes()
        db = Database(root / "attendance_system.db")
        with patch.object(migration, "BASE_DIR", root), patch.object(migration, "LEGACY_FILES", (source, root / "attendance" / "attendance.db")):
            migration.bootstrap(db)
            migration.bootstrap(db)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(len(db.exams()), 1)
        self.assertEqual(db.exams()[0]["roster_complete"], 0)
        self.assertEqual(db.records()[0]["verification_method"], "legacy_unverified")

    def test_additive_exam_description_migration_preserves_existing_rows(self):
        old = Database(Path(self.temp.name) / 'old.db')
        with closing(sqlite3.connect(old.path)) as conn:
            conn.execute("""CREATE TABLE exams(id INTEGER PRIMARY KEY, name TEXT, exam_date TEXT,
                start_time TEXT, end_time TEXT, status TEXT, created_at TEXT, roster_complete INTEGER)""")
            conn.execute("INSERT INTO exams VALUES(1,'Preserved','2025-01-01','09:00','10:00','ended','2025-01-01',0)")
            conn.commit()
        old.init()
        old.init()
        self.assertEqual(old.exam(1)['name'], 'Preserved')
        self.assertEqual(old.exam(1)['description'], '')

    def test_simultaneous_attendance_is_unique(self):
        self.db.add_student('A', 'Alice')
        exam = self.db.create_exam('Race', '2026-10-17', '09:00', '10:00', ['A'])
        self.db.set_exam_status(exam, 'active')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.db.record_attendance(exam, 'A'), range(4)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(len(self.db.records(exam)), 1)


if __name__ == "__main__":
    unittest.main()
