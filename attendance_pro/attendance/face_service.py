"""Enrollment and best-distance face recognition. Heavy native imports are lazy."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import logging

from .config import Settings, get_settings
from .db import Database

LOG = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def encode_image(data: bytes):
    import cv2
    import face_recognition
    import numpy as np
    if not data or len(data) > 12 * 1024 * 1024:
        raise ValueError("Image must be between 1 byte and 12 MB")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unreadable image")
    if image.shape[0] * image.shape[1] > 12_000_000:
        raise ValueError("Image dimensions are too large (maximum 12 megapixels)")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    try:
        locations = face_recognition.face_locations(rgb)
    except RuntimeError as exc:
        if "Unsupported image type" in str(exc):
            raise RuntimeError("dlib rejected an RGB image. Rebuild with compatible NumPy and dlib versions") from exc
        raise
    if len(locations) != 1:
        raise ValueError(f"Enrollment image must contain exactly one face (found {len(locations)})")
    embeddings = face_recognition.face_encodings(rgb, locations)
    if len(embeddings) != 1:
        raise ValueError("Could not encode the detected face")
    return np.asarray(embeddings[0], dtype=np.float64)


def enroll_bytes(db: Database, student_id: str, filename: str, data: bytes,
                 settings: Settings | None = None) -> Path:
    import numpy as np
    settings = settings or get_settings()
    if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Use a JPG, PNG, or BMP image")
    embedding = encode_image(data)
    digest = sha256(data).hexdigest()
    with db.connect() as conn:
        if not conn.execute("SELECT 1 FROM students WHERE student_id=? AND active=1", (student_id,)).fetchone():
            raise ValueError("Register an active student before face enrollment")
        existing = conn.execute("SELECT student_id FROM face_enrollments WHERE image_sha256=?", (digest,)).fetchone()
        if existing and existing[0] != student_id:
            raise ValueError("This image is already enrolled for another student")
    for existing in db.enrollments():
        vector = np.frombuffer(existing["embedding"], dtype=np.float64)
        if existing["student_id"] != student_id and vector.size == 128:
            if np.linalg.norm(vector - embedding) <= settings.tolerance:
                raise ValueError(f"Face closely matches already enrolled student {existing['student_id']}")
    root = settings.known_faces_dir.resolve()
    folder = root / sha256(student_id.encode()).hexdigest()[:20]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (digest + Path(filename).suffix.lower())
    path.write_bytes(data)
    db.save_enrollment(student_id, str(path.relative_to(root)), embedding.tobytes(), digest)
    return path


class FaceRecognizer:
    def __init__(self, db: Database, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        if not self.settings.landmarks_path.is_file():
            raise FileNotFoundError(f"Landmark model missing: {self.settings.landmarks_path}")
        try:
            import dlib
            self.predictor = dlib.shape_predictor(str(self.settings.landmarks_path))
        except Exception as exc:
            raise RuntimeError(f"Could not load landmark model: {exc}") from exc
        self.reload()

    def reload(self) -> None:
        import numpy as np
        self.identities = []
        self.encodings = []
        for row in self.db.enrollments():
            vector = np.frombuffer(row["embedding"], dtype=np.float64)
            if vector.size == 128:
                self.identities.append((row["student_id"], row["name"]))
                self.encodings.append(vector)
            else:
                LOG.warning("Skipping an invalid enrolled face template")

    def best_match(self, encoding):
        import face_recognition
        if not self.encodings:
            return None
        distances = face_recognition.face_distance(self.encodings, encoding)
        best = int(distances.argmin())
        return self.identities[best] if distances[best] <= self.settings.tolerance else None

    @staticmethod
    def _ear(points) -> float:
        import numpy as np
        horizontal = np.linalg.norm(points[0]-points[3])
        if horizontal == 0:
            return 0.0
        return float((np.linalg.norm(points[1]-points[5]) +
                      np.linalg.norm(points[2]-points[4])) / (2*horizontal))

    def recognize(self, frame):
        import cv2
        import dlib
        import face_recognition
        import numpy as np
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model=self.settings.model)
        if len(locations) != 1:
            return {"face_count": len(locations), "identity": None, "name": None, "ear": None}
        encodings = face_recognition.face_encodings(rgb, locations)
        if len(encodings) != 1:
            return {"face_count": 1, "identity": None, "name": None, "ear": None}
        match = self.best_match(encodings[0])
        top, right, bottom, left = locations[0]
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 145, 140) if match else (40, 70, 210), 2)
        if not match:
            return {"face_count": 1, "identity": None, "name": None, "ear": None}
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        shape = self.predictor(gray, dlib.rectangle(left, top, right, bottom))
        points = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)])
        ear = (self._ear(points[36:42]) + self._ear(points[42:48])) / 2
        return {"face_count": 1, "identity": match[0], "name": match[1], "ear": ear}
