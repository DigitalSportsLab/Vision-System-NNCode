from pydantic import BaseSettings, AnyHttpUrl
from typing import List

class Settings(BaseSettings):
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["*"]

    YOLO_DETECT: str = "yolov8s.pt"
    YOLO_SEG: str = "yolov8n-seg.pt"
    YOLO_POSE: str = "yolov8n-pose.pt"

    UPLOADS_DIR: str = "data/uploads"

    class Config:
        env_file = ".env"

settings = Settings()
