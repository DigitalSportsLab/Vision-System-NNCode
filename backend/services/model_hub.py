# backend/services/model_hub.py
from __future__ import annotations
import logging

from backend.services.models.interfaces import ModelTask, ModelAdapter
from backend.services.models.registry import registry, ModelSpec
from backend.services.models.adapters.yolo import YoloAdapter

log = logging.getLogger("app")  # nutzt deinen App-Logger

# --- Default-Registrierungen (YOLO mit Version & Task) ----------------------

def _register_default_yolo_models():
    defaults = [
        ("yolo/v8s:detect",   "v8s", ModelTask.detect,   "yolov8s.pt"),
        ("yolo/v8n:segment",  "v8n", ModelTask.segment,  "yolov8n-seg.pt"),
        ("yolo/v8n:pose",     "v8n", ModelTask.pose,     "yolov8n-pose.pt"),
        ("yolo/v8s:classify", "v8s", ModelTask.classify, "yolov8s-cls.pt"),
        # hier kannst du jederzeit weitere Modelle/Versionen ergänzen:
        # ("yolo/v9m:detect", "v9m", ModelTask.detect, "yolov9m.pt"),
    ]
    for key, version, task, weights in defaults:
        try:
            registry.register(ModelSpec(
                key=key,
                provider="yolo",
                version=version,
                task=task,
                weights=weights,
                factory=lambda w, t, v: YoloAdapter(w, t, v)
            ))
        except ValueError:
            # bereits registriert → ignorieren
            pass

_register_default_yolo_models()

# --- Public API -------------------------------------------------------------

def load_adapter_by_key(key: str) -> ModelAdapter:
    """Strikter Loader: erfordert registrierten Key, sonst Exception."""
    spec = registry.get(key)
    adapter = spec.factory(spec.weights, spec.task, spec.version)
    adapter.warmup()
    return adapter

def resolve_key_from_legacy(model_type: str) -> str:
    """
    Mapping für bestehende API-Bodies (z. B. 'objectDetection').
    So bleibt dein Frontend kompatibel.
    """
    mapping = {
        "objectDetection": "yolo/v8s:detect",
        "segmentation":    "yolo/v8n:segment",
        "pose":            "yolo/v8n:pose",
        "classification":  "yolo/v8s:classify",
    }
    if model_type not in mapping:
        raise ValueError(f"Unsupported model_type: {model_type}")
    return mapping[model_type]

# --- Fallback-Mechanismus (YOLO als Default) --------------------------------

def get_default_adapter_for(model_type: str) -> ModelAdapter:
    """
    Legacy-Fallback: direkt einen YoloAdapter bauen – wie früher hardcodiert.
    """
    mapping = {
        "objectDetection": ("yolov8s.pt",     ModelTask.detect,   "v8s"),
        "segmentation":    ("yolov8n-seg.pt", ModelTask.segment,  "v8n"),
        "pose":            ("yolov8n-pose.pt",ModelTask.pose,     "v8n"),
        "classification":  ("yolov8s-cls.pt", ModelTask.classify, "v8s"),
    }
    weights, task, version = mapping.get(
        model_type, ("yolov8s.pt", ModelTask.detect, "v8s")
    )
    return YoloAdapter(weights, task, version)

def load_adapter_by_key_safe(key: str, model_type: str) -> tuple[ModelAdapter, str]:
    """
    Bevorzugt Registry; wenn der Key fehlt/fehlschlägt → YOLO-Default.
    Gibt (adapter, resolved_key) zurück. Loggt WARN beim Fallback.
    """
    try:
        spec = registry.get(key)
        adapter = spec.factory(spec.weights, spec.task, spec.version)
        adapter.warmup()
        return adapter, key
    except Exception as e:
        adapter = get_default_adapter_for(model_type)
        fallback_key = f"yolo/{adapter.version}:{adapter.task.value}"
        log.warning(
            "Model key '%s' not found or failed (%s). Falling back to '%s'.",
            key, str(e), fallback_key
        )
        return adapter, fallback_key
