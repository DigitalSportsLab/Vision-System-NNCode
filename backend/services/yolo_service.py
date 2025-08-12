from ultralytics import YOLO

class YoloService:
    _cache: dict[str, YOLO] = {}

    @classmethod
    def get(cls, task: str, weights: str) -> YOLO:
        key = f"{task}:{weights}"
        if key not in cls._cache:
            cls._cache[key] = YOLO(weights)
        return cls._cache[key]
