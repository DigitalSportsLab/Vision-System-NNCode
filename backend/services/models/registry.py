from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict
from backend.services.models.interfaces import ModelTask, ModelAdapter


@dataclass(frozen=True)
class ModelSpec:
    """Beschreibt ein Modell eindeutig."""
    key: str                  # z. B. "yolo/v8n:detect"
    provider: str              # "yolo", "onnx", ...
    version: str               # z. B. "v8n"
    task: ModelTask            # detect, pose, segment ...
    weights: str               # Pfad oder Modellname
    factory: Callable[[str, ModelTask, str], ModelAdapter]


class ModelRegistry:
    def __init__(self):
        self._specs: Dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec):
        if spec.key in self._specs:
            raise ValueError(f"Model key already registered: {spec.key}")
        self._specs[spec.key] = spec

    def get(self, key: str) -> ModelSpec:
        if key not in self._specs:
            raise KeyError(f"Unknown model key: {key}")
        return self._specs[key]

    def all(self) -> Dict[str, ModelSpec]:
        return dict(self._specs)


# Singleton-Instanz
registry = ModelRegistry()
