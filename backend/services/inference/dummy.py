# backend/services/inference/dummy.py
import time
from typing import List
from backend.core.pipeline import Frame, InferenceResult, Detection

class DummyInference:
    """Platzhalter – liefert keine Detections. Später durch echtes Pose-Modell ersetzen."""
    def infer(self, frame: Frame) -> InferenceResult:
        return InferenceResult(ts_ms=frame.ts_ms, detections=[])
