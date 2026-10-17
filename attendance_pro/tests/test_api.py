import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from itertools import chain, repeat
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from api.main import create_app
from attendance.db import Database


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db_path = Path(self.folder.name) / "api.db"
        self.db = Database(self.db_path)
        self.db.init()
        self.db.add_student("S-001", "Test Student")
        self.exam_id = self.db.create_exam("Physics", "2026-11-01", "09:00", "10:00", ["S-001"])
        self.app = create_app(self.db_path)

    def test_overview_and_session_lifecycle_use_real_database(self):
        with TestClient(self.app) as client:
            overview = client.get("/api/overview")
            self.assertEqual(overview.status_code, 200)
            self.assertEqual(overview.json()["metrics"]["students"], 1)
            self.assertEqual(overview.json()["featured"]["name"], "Physics")
            self.assertEqual(client.get("/api/session/status").json()["camera"], "paused")
            self.assertEqual(client.post(f"/api/exams/{self.exam_id}/start").status_code, 200)
            self.assertEqual(client.get("/api/session/status").json()["exam"]["status"], "active")
            self.assertEqual(client.post(f"/api/exams/{self.exam_id}/start").status_code, 409)
            self.assertEqual(client.post("/api/exams/999/end").status_code, 404)
            self.assertEqual(self.db.exam(self.exam_id)["status"], "active")
            self.assertEqual(client.post(f"/api/exams/{self.exam_id}/end").status_code, 200)
            self.assertEqual(self.db.exam(self.exam_id)["status"], "ended")

    def test_verified_event_records_once_and_uses_roster_gate(self):
        with TestClient(self.app) as client:
            client.post(f"/api/exams/{self.exam_id}/start")
            camera = Mock()
            camera.thread.is_alive.return_value = True
            camera.stop_event.is_set.return_value = False
            camera.close.return_value = True
            camera.frame.return_value = None
            events = [
                {"events": [("S-001", "Test Student")], "identity_id": "S-001", "identity": "Test Student",
                 "stage": "Verified", "feedback": "Blink verified", "face_count": 1, "error": None},
                {"events": [("S-001", "Test Student")], "identity_id": "S-001", "identity": "Test Student",
                 "stage": "Verified", "feedback": "Blink verified", "face_count": 1, "error": None},
            ]
            camera.snapshot.side_effect = chain(events, repeat({
                "events": [], "identity_id": "S-001", "identity": "Test Student",
                "stage": "Verified", "feedback": "Blink verified", "face_count": 1, "error": None,
            }))
            self.app.state.session.camera = camera
            self.app.state.session.exam_id = self.exam_id
            self.app.state.session._process_once(camera)
            first = client.get("/api/session/status").json()
            self.assertEqual(first["stage"], "Recorded")
            self.assertEqual(first["outcome"]["kind"], "recorded")
            self.assertEqual(len(self.db.records(self.exam_id)), 1)
            self.app.state.session._process_once(camera)
            second = client.get("/api/session/status").json()
            self.assertEqual(second["outcome"]["kind"], "rejected")
            self.assertIn("already recorded", second["outcome"]["message"])
            self.assertEqual(len(self.db.records(self.exam_id)), 1)
            self.assertEqual(client.get("/api/session/frame").status_code, 404)

    def test_verified_unassigned_identity_is_rejected(self):
        with TestClient(self.app) as client:
            self.db.add_student('S-002', 'Unassigned')
            client.post(f'/api/exams/{self.exam_id}/start')
            camera = Mock()
            camera.snapshot.return_value = {'events': [('S-002', 'Unassigned')], 'identity_id': 'S-002',
                'identity': 'Unassigned', 'stage': 'Verified', 'feedback': 'Blink verified', 'face_count': 1, 'error': None}
            self.app.state.session.camera = camera
            self.app.state.session.exam_id = self.exam_id
            self.app.state.session._process_once(camera)
            self.assertEqual(self.db.records(self.exam_id), [])
            self.assertIn('not assigned', self.app.state.session.last_outcome['message'])
            camera.close.return_value = True
            self.app.state.session.stop_camera()

    def test_event_pump_records_without_a_browser_poll(self):
        with TestClient(self.app) as client:
            client.post(f"/api/exams/{self.exam_id}/start")
            camera = Mock()
            camera.thread.is_alive.return_value = True
            camera.stop_event.is_set.return_value = False
            camera.close.return_value = True
            camera.snapshot.side_effect = chain([{
                "events": [("S-001", "Test Student")], "identity_id": "S-001", "identity": "Test Student",
                "stage": "Verified", "feedback": "Blink verified", "face_count": 1, "error": None,
            }], repeat({
                "events": [], "identity_id": "S-001", "identity": "Test Student",
                "stage": "Verified", "feedback": "Blink verified", "face_count": 1, "error": None,
            }))
            with patch("api.session.FaceRecognizer"), patch("api.session.LocalCameraSession", return_value=camera):
                self.app.state.session.start_camera()
                for _ in range(30):
                    if self.db.records(self.exam_id):
                        break
                    time.sleep(.05)
                self.assertEqual(len(self.db.records(self.exam_id)), 1)
                self.app.state.session.stop_camera()

    def test_react_workflow_uses_isolated_enrollment_and_real_analytics(self):
        import numpy as np
        with TestClient(self.app) as client:
            created = client.post('/api/students', json={'student_id': 'S-002', 'name': 'New Student'})
            self.assertEqual(created.status_code, 201)
            self.assertEqual(client.post('/api/students', json={'student_id': 'S-002', 'name': 'Duplicate'}).status_code, 409)
            self.assertEqual(client.post('/api/students', json={'student_id': ' ', 'name': 'Blank'}).status_code, 422)
            self.assertEqual(client.post('/api/students', json={'student_id': 'bad/id', 'name': 'Unsafe'}).status_code, 422)
            with patch('attendance.face_service.encode_image', return_value=np.zeros(128, dtype=np.float64)):
                upload = client.post('/api/students/S-002/enrollment?filename=consented.jpg',
                                     content=b'isolated-test-image', headers={'Content-Type': 'image/jpeg'})
            self.assertEqual(upload.status_code, 200, upload.text)
            self.assertTrue((self.db_path.with_suffix('.faces')).exists())
            self.assertEqual(next(row['enrolled'] for row in client.get('/api/students').json()
                                  if row['student_id'] == 'S-002'), 1)
            self.assertEqual(client.post('/api/students/S-002/enrollment?filename=bad.txt',
                         content=b'x', headers={'Content-Type': 'text/plain'}).status_code, 415)
            response = client.post('/api/exams', json={'name': 'New practical', 'exam_date': '2026-10-17',
                'start_time': '09:00', 'end_time': '10:00', 'description': 'Room 101', 'student_ids': ['S-002']})
            self.assertEqual(response.status_code, 201, response.text)
            new_id = response.json()['exam']['id']
            self.assertEqual(response.json()['exam']['description'], 'Room 101')
            self.assertEqual(client.put(f'/api/exams/{new_id}/roster', json={'student_ids': ['S-001', 'S-002']}).status_code, 200)
            self.assertEqual(client.get(f'/api/exams/{new_id}/roster').json()['summary']['assigned'], 2)
            self.assertEqual(client.post(f'/api/exams/{new_id}/start').status_code, 200)
            self.assertTrue(self.db.record_attendance(new_id, 'S-001'))
            self.assertFalse(self.db.record_attendance(new_id, 'S-001'))
            report = client.get(f'/api/analytics?exam_id={new_id}').json()
            self.assertEqual(report['exams'][0]['summary']['rate'], 50.0)
            self.assertEqual(len(report['records']), 1)
            self.assertEqual(client.put(f'/api/exams/{new_id}/roster', json={'student_ids': ['S-001']}).status_code, 409)
            self.assertEqual(client.get('/api/analytics?exam_date=bad').status_code, 422)
            self.assertEqual(client.post(f'/api/exams/{new_id}/end').status_code, 200)

    def test_camera_binding_prevents_event_from_crossing_exam_sessions(self):
        with TestClient(self.app) as client:
            second = self.db.create_exam('Second', '2026-11-01', '10:00', '11:00', ['S-001'])
            client.post(f'/api/exams/{self.exam_id}/start')
            camera = Mock()
            camera.snapshot.return_value = {'events': [('S-001', 'Test Student')], 'identity_id': 'S-001',
                'identity': 'Test Student', 'stage': 'Verified', 'feedback': 'Blink verified', 'face_count': 1, 'error': None}
            self.app.state.session.camera = camera
            self.app.state.session.exam_id = self.exam_id
            self.db.set_exam_status(self.exam_id, 'ended')
            self.db.set_exam_status(second, 'active')
            self.app.state.session._process_once(camera)
            self.assertEqual(self.db.records(second), [])
            self.assertEqual(self.app.state.session.last_outcome['kind'], 'error')
            camera.close.return_value = True
            self.app.state.session.stop_camera()

    def test_concurrent_exam_starts_and_origin_rejection(self):
        with TestClient(self.app) as client:
            other = self.db.create_exam('Other', '2026-11-02', '09:00', '10:00', ['S-001'])
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda exam_id: client.post(f'/api/exams/{exam_id}/start').status_code,
                                        [self.exam_id, other]))
            self.assertEqual(sorted(results), [200, 409])
            self.assertEqual(sum(e['status'] == 'active' for e in self.db.exams()), 1)
            forbidden = client.post('/api/students', json={'student_id': 'X', 'name': 'Outside'},
                                    headers={'Origin': 'https://outside.example'})
            self.assertEqual(forbidden.status_code, 403)
            self.assertEqual(client.get('/api/session/frame', headers={'Sec-Fetch-Site': 'cross-site'}).status_code, 403)
            self.assertFalse(any(s['student_id'] == 'X' for s in self.db.students()))


if __name__ == "__main__":
    unittest.main()
