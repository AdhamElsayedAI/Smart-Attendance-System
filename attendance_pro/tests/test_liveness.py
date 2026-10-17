import unittest

from attendance.liveness_service import BlinkChallenge


class BlinkTests(unittest.TestCase):
    def test_valid_sequence_and_insufficient_closure(self):
        challenge = BlinkChallenge(stable_frames=2, closed_frames=2)
        self.assertFalse(challenge.observe("A", .3, 1, 1).verified)
        self.assertFalse(challenge.observe("A", .3, 1, 2).verified)
        self.assertFalse(challenge.observe("A", .1, 1, 3).verified)
        self.assertFalse(challenge.observe("A", .3, 1, 4).verified)
        challenge.observe("A", .1, 1, 5)
        challenge.observe("A", .1, 1, 6)
        self.assertTrue(challenge.observe("A", .3, 1, 7).verified)

    def test_identity_switch_unknown_and_multiple_faces_reset(self):
        challenge = BlinkChallenge(stable_frames=1, closed_frames=2)
        challenge.observe("A", .1, 1, 1)
        challenge.observe("A", .1, 1, 2)
        self.assertFalse(challenge.observe("B", .3, 1, 3).verified)
        challenge.observe("B", .1, 1, 4)
        self.assertFalse(challenge.observe(None, None, 1, 5).verified)
        challenge.observe("B", .1, 1, 6)
        self.assertFalse(challenge.observe("B", .3, 2, 7).verified)
        self.assertFalse(challenge.observe("B", .3, 1, 8).verified)

    def test_verification_expiration(self):
        challenge = BlinkChallenge(stable_frames=1, closed_frames=1, expiry_seconds=3)
        challenge.observe("A", .1, 1, 1)
        self.assertTrue(challenge.observe("A", .3, 1, 2).verified)
        self.assertTrue(challenge.observe("A", .3, 1, 3).verified)
        self.assertFalse(challenge.observe("A", .3, 1, 6).verified)


if __name__ == "__main__":
    unittest.main()
