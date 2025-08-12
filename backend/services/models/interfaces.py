from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class ModelTask(str, Enum):
    detect = "detect"        # Objekterkennung
    segment = "segment"      # Segmentierung
    pose = "pose"            # Pose-Estimation
    classify = "classify"    # Bildklassifikation
    track = "track"          # Objekt-Tracking
    depth    = "depth"     
    normals  = "normals"
    custom = "custom"        # Für spätere Spezialfälle


@dataclass
class InferenceResult:
    """Einheitliches Ergebnis für alle Modelle."""
    raw: Any                          # Provider-spezifisches Roh-Objekt
    names: dict[int, str] | list[str] # Klassenlabels


class ModelAdapter(Protocol):
    """Interface für alle Modelladapter."""
    task: ModelTask
    version: str                      # z. B. "v8n", "v8s", "v9m"
    provider: str                     # z. B. "yolo", "onnx", "openvino"

    def predict(self, frame: Any) -> InferenceResult: ...
    def warmup(self) -> None: ...
    def close(self) -> None: ...
