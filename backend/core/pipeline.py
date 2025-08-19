# backend/core/pipeline.py
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, runtime_checkable, Optional

@dataclass
class Frame:
    ts_ms: int
    image: Any  # np.ndarray oder None (für Headless/Dummy)
    meta: Dict[str, Any]

@dataclass
class Detection:
    label: str                   # "player" | "ball" | ...
    bbox: List[float]            # [x, y, w, h] (0..1 normiert)
    score: float
    keypoints: Optional[Dict[str, List[float]]] = None  # {"knee_l":[x,y,conf], ...}

@dataclass
class InferenceResult:
    ts_ms: int
    detections: List[Detection]

@runtime_checkable
class Source(Protocol):
    def open(self) -> None: ...
    def read(self) -> Optional[Frame]: ...
    def close(self) -> None: ...

@runtime_checkable
class Inference(Protocol):
    def infer(self, frame: Frame) -> InferenceResult: ...

@runtime_checkable
class Tracker(Protocol):
    def update(self, infer: InferenceResult) -> Dict[str, Any]:
        """
        Rückgabe z.B.:
        {
          "tracks": [{"track_id": 1, "label":"player", "bbox":[...], "keypoints":{...}}, ...],
          "raw": InferenceResult (optional)
        }
        """
        ...

@runtime_checkable
class Sink(Protocol):
    def write(self, session_id: int, payload: Dict[str, Any]) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...

class Pipeline:
    def __init__(self, source: Source, inference: Inference, tracker: Tracker, sinks: List[Sink]):
        self.source = source
        self.inference = inference
        self.tracker = tracker
        self.sinks = sinks
        self._open = False

    def open(self):
        if not self._open:
            self.source.open()
            self._open = True

    def step(self, session_id: int) -> bool:
        """Liest 1 Frame, macht Inference, Tracking, schreibt in alle Sinks.
        Rückgabe False, wenn Quelle fertig/leer."""
        frm = self.source.read()
        if frm is None:
            return False
        inf = self.inference.infer(frm)
        tracked = self.tracker.update(inf)
        for s in self.sinks:
            s.write(session_id, tracked)
        return True

    def close(self):
        self.source.close()
        for s in self.sinks:
            s.flush()
            s.close()
        self._open = False
