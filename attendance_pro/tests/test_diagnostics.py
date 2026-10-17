import unittest
from unittest.mock import Mock

from attendance.camera_service import CameraLease
from attendance.diagnostics import probe_camera


class CameraProbeTests(unittest.TestCase):
    def test_probe_respects_existing_camera_lease(self):
        lease = CameraLease(113)
        lease.acquire()
        module = Mock()
        try:
            state, message = probe_camera(113, module)
            self.assertEqual(state, "Unavailable")
            self.assertIn("another AttendanceOS process", message)
            module.VideoCapture.assert_not_called()
        finally:
            lease.release()

    def test_probe_releases_camera_on_success_failure_and_exception(self):
        for opened in (True, False):
            with self.subTest(opened=opened):
                capture = Mock()
                capture.isOpened.return_value = opened
                state, _ = probe_camera(2, Mock(VideoCapture=Mock(return_value=capture)))
                self.assertEqual(state, "Available" if opened else "Unavailable")
                capture.release.assert_called_once()
        capture = Mock()
        capture.isOpened.side_effect = RuntimeError("device error")
        state, _ = probe_camera(2, Mock(VideoCapture=Mock(return_value=capture)))
        self.assertEqual(state, "Unavailable")
        capture.release.assert_called_once()
