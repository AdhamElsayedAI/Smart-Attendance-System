"""Single-face, identity-bound blink challenge state machine."""
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class LivenessResult:
    message: str
    verified: bool = False
    stable_frames: int = 0


class BlinkChallenge:
    def __init__(self, ear_threshold: float = 0.21, closed_frames: int = 2,
                 stable_frames: int = 3, expiry_seconds: int = 12):
        self.ear_threshold = ear_threshold
        self.closed_frames_needed = closed_frames
        self.stable_frames_needed = stable_frames
        self.expiry_seconds = expiry_seconds
        self.reset()

    def reset(self) -> None:
        self.identity: str | None = None
        self.stable = 0
        self.closed = 0
        self.verified_until = 0.0
        self.last_seen = 0.0

    def observe(self, identity: str | None, ear: float | None, face_count: int,
                now: float | None = None) -> LivenessResult:
        current = time.monotonic() if now is None else now
        if face_count != 1:
            self.reset()
            return LivenessResult("Show exactly one face to the camera")
        if identity is None or ear is None:
            self.reset()
            return LivenessResult("Face unknown or landmarks unavailable")
        if identity != self.identity or (self.last_seen and current-self.last_seen > self.expiry_seconds):
            self.reset()
            self.identity = identity
        self.last_seen = current
        self.stable += 1
        if self.stable < self.stable_frames_needed:
            self.closed = 0
            return LivenessResult("Hold still for identity confirmation", stable_frames=self.stable)
        if self.verified_until > current:
            return LivenessResult("Blink verified", True, self.stable)
        if ear < self.ear_threshold:
            self.closed += 1
            return LivenessResult("Eyes closed — reopen to complete blink", stable_frames=self.stable)
        if self.closed >= self.closed_frames_needed:
            self.closed = 0
            self.verified_until = current + self.expiry_seconds
            return LivenessResult("Blink verified", True, self.stable)
        self.closed = 0
        return LivenessResult("Blink once to verify", stable_frames=self.stable)
