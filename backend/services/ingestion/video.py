# backend/services/ingestion/video.py
import time
from typing import Optional, Dict, Any
from backend.core.pipeline import Frame
try:
    import cv2
except Exception:
    cv2 = None

class VideoSource:
    """Einheitliche Quelle für RTSP/Datei/Webcam. Gibt normierte Frames zurück."""
    def __init__(self, stream_url: str, resize_wh: Optional[tuple[int,int]] = None):
        self.url = stream_url
        self.cap = None
        self.resize_wh = resize_wh

    def open(self) -> None:
        if cv2 is None:
            self.cap = None
            return
        self.cap = cv2.VideoCapture(self.url)

    def read(self) -> Optional[Frame]:
        ts_ms = int(time.time() * 1000)
        if self.cap is None:
            # headless/dummy
            return Frame(ts_ms=ts_ms, image=None, meta={"dummy": True})
        ok, img = self.cap.read()
        if not ok:
            return None
        if self.resize_wh:
            img = cv2.resize(img, self.resize_wh)
        h, w = img.shape[:2]
        return Frame(ts_ms=ts_ms, image=img, meta={"w": w, "h": h})

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
