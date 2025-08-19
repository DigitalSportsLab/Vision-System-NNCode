# backend/services/tracking/naive.py
from typing import Dict, Any
from backend.core.pipeline import InferenceResult

class NaiveTracker:
    """Durchreicht Detections ohne ID-Zuweisung (MVP)."""
    def update(self, infer: InferenceResult) -> Dict[str, Any]:
        tracks = []
        for det in infer.detections:
            tracks.append({
                "track_id": None,  # in späteren Versionen vergeben
                "label": det.label,
                "bbox": det.bbox,
                "keypoints": det.keypoints,
                "score": det.score,
                "ts_ms": infer.ts_ms,
            })
        return {"tracks": tracks}
