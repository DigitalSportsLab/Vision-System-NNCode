# backend/workers/camera_worker.py
import time

from backend.core.pipeline import Pipeline
from backend.services.ingestion.video import VideoSource
from backend.services.inference.dummy import DummyInference
from backend.services.tracking.naive import NaiveTracker
from backend.services.storage import DbSink

class CameraWorker:
    def __init__(self, stream_url: str, session_id: int, fps_target: int = 25):
        self.stream_url = stream_url
        self.session_id = session_id
        self.fps_target = max(1, fps_target)
        self.pipeline = Pipeline(
            source=VideoSource(stream_url),
            inference=DummyInference(),
            tracker=NaiveTracker(),
            sinks=[DbSink(batch_size=64)]
        )
        self._stop = False

    def run(self):
        period = 1.0 / self.fps_target
        self.pipeline.open()
        last = 0.0
        try:
            while not self._stop:
                now = time.time()
                if now - last < period:
                    time.sleep(0.001)
                    continue
                last = now
                ok = self.pipeline.step(session_id=self.session_id)
                if not ok:
                    # Quelle leer/Fehler – kurze Pause, dann weiter versuchen
                    time.sleep(0.1)
        finally:
            self.pipeline.close()

    def stop(self):
        self._stop = True
