from dataclasses import dataclass
from functools import lru_cache

import cv2


@dataclass
class DetectionSummary:
    person_count: int = 0
    face_count: int = 0
    has_person: bool = False
    has_face: bool = False


@lru_cache(maxsize=1)
def get_face_detector():
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    return cv2.CascadeClassifier(cascade_path)


@lru_cache(maxsize=1)
def get_person_detector():
    try:
        from ultralytics import YOLO

        return YOLO("yolov8n.pt")
    except Exception:
        return None


def _detect_faces(image) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = get_face_detector()
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    return len(faces)


def _detect_people(image_path: str) -> int:
    detector = get_person_detector()
    if detector is None:
        return 0
    try:
        results = detector.predict(image_path, classes=[0], verbose=False)
    except Exception:
        return 0
    if not results:
        return 0
    boxes = getattr(results[0], "boxes", None)
    if boxes is None:
        return 0
    return len(boxes)


def detect_people_and_faces(image_path: str) -> DetectionSummary:
    image = cv2.imread(image_path)
    if image is None:
        return DetectionSummary()
    face_count = _detect_faces(image)
    person_count = _detect_people(image_path)
    return DetectionSummary(
        person_count=person_count,
        face_count=face_count,
        has_person=person_count > 0,
        has_face=face_count > 0,
    )
