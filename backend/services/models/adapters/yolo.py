from __future__ import annotations
from ultralytics import YOLO
from typing import Any
from backend.services.models.interfaces import ModelAdapter, ModelTask, InferenceResult


class YoloAdapter(ModelAdapter):
    def __init__(self, weights_path: str, task: ModelTask, version: str):
        self._model = YOLO(weights_path)
        self.task = task
        self.version = version
        self.provider = "yolo"

    def warmup(self) -> None:
        # Optional: Model vorbereiten
        pass

    def predict(self, frame: Any) -> InferenceResult:
        results = self._model(frame)
        r0 = results[0]
        names = getattr(r0, "names", {})
        return InferenceResult(raw=r0, names=names)

    def close(self) -> None:
        pass
