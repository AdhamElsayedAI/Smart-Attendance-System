import tempfile
import unittest
from collections import deque
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from attendance.config import get_settings
from attendance.db import Database
from attendance.face_service import FaceRecognizer, encode_image, enroll_bytes
from attendance.camera_service import LocalCameraSession
from attendance.liveness_service import BlinkChallenge


class FaceAndCameraTests(unittest.TestCase):
    def test_empty_enrollment_and_threshold_best_match(self):
        recognizer = FaceRecognizer.__new__(FaceRecognizer)
        recognizer.encodings = []
        recognizer.identities = []
        recognizer.settings = get_settings()
        self.assertIsNone(recognizer.best_match(np.zeros(128)))
        recognizer.encodings = [np.zeros(128), np.ones(128)]
        recognizer.identities = [("A", "Alice"), ("B", "Bob")]
        self.assertEqual(recognizer.best_match(np.zeros(128)), ("A", "Alice"))
        self.assertIsNone(recognizer.best_match(np.full(128, .5)))

    def test_invalid_image_and_missing_model(self):
        with self.assertRaises(ValueError):
            encode_image(b"not an image")
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "db.sqlite")
            db.init()
            db.add_student("A", "Alice")
            with self.assertRaises(ValueError):
                enroll_bytes(db, "A", "photo.txt", b"x")
            settings = get_settings()
            from dataclasses import replace
            with self.assertRaises(FileNotFoundError):
                FaceRecognizer(db, replace(settings, landmarks_path=Path(folder) / "missing.dat"))

    def test_enrollment_rejects_no_face_and_multiple_faces(self):
        import cv2
        import face_recognition
        _, png = cv2.imencode(".png", np.zeros((12, 12, 3), dtype=np.uint8))
        for locations in ([], [(0, 1, 1, 0), (1, 2, 2, 1)]):
            with self.subTest(face_count=len(locations)):
                with patch.object(face_recognition, "face_locations", return_value=locations):
                    with self.assertRaises(ValueError):
                        encode_image(png.tobytes())

    def test_duplicate_face_identity_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "db.sqlite")
            db.init()
            db.add_student("A", "Alice")
            db.add_student("B", "Bob")
            db.save_enrollment("A", "alice.jpg", np.zeros(128, dtype=np.float64).tobytes(), "old-hash")
            from dataclasses import replace
            settings = replace(get_settings(), known_faces_dir=Path(folder) / "faces")
            with patch("attendance.face_service.encode_image", return_value=np.zeros(128)):
                with self.assertRaisesRegex(ValueError, "closely matches"):
                    enroll_bytes(db, "B", "bob.jpg", b"different picture", settings)

    def test_multiple_faces_rejected_before_matching(self):
        import cv2
        import face_recognition
        recognizer = FaceRecognizer.__new__(FaceRecognizer)
        recognizer.settings = get_settings()
        with patch.object(face_recognition, "face_locations", return_value=[(0, 1, 1, 0), (1, 2, 2, 1)]):
            outcome = recognizer.recognize(np.zeros((10, 10, 3), dtype=np.uint8))
        self.assertEqual(outcome["face_count"], 2)
        self.assertIsNone(outcome["identity"])

    def test_missing_camera_releases_device(self):
        import cv2
        from unittest.mock import Mock
        capture = Mock()
        capture.isOpened.return_value = False
        with patch.object(cv2, "VideoCapture", return_value=capture):
            with self.assertRaises(RuntimeError):
                LocalCameraSession(None, get_settings())
        capture.release.assert_called_once()

    def test_camera_emits_once_per_blink_and_rearms_after_face_leaves(self):
        camera = LocalCameraSession.__new__(LocalCameraSession)
        camera.challenge = BlinkChallenge(stable_frames=1, closed_frames=1)
        camera.settings = SimpleNamespace(stable_frames=1)
        camera.lock = Lock()
        camera.events = deque(maxlen=16)
        camera.verification_emitted = False
        known = {"identity": "A", "name": "Alice", "face_count": 1, "ear": .3}
        closed = {**known, "ear": .1}
        missing = {"identity": None, "name": None, "face_count": 0, "ear": None}
        for result in (known, closed, known, known):
            camera._update_recognition(result)
        self.assertEqual(list(camera.events), [("A", "Alice")])
        camera._update_recognition(missing)
        for result in (known, closed, known):
            camera._update_recognition(result)
        self.assertEqual(list(camera.events), [("A", "Alice"), ("A", "Alice")])


if __name__ == "__main__":
    unittest.main()
