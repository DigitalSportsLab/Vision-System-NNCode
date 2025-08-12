import cv2
import threading
from backend.services.frame_processor import process_frame
from backend.services.detection_service import save_event
from backend.services.camera_manager import video_captures, camera_running, set_latest
from backend.db_settings import SessionLocal
from backend.monitoring.metrics import metrics

def run_camera_loop(camera_id: int, stream_url: str, adapter, model_task: str, thread_name: str):
    """
    Liest einen Live-Stream (RTSP/USB/HTTP), nutzt das generische ModelAdapter-Interface.
    Metriken:
      - frame_processing_duration_seconds wird im frame_processor gemessen (measure_latency)
      - detections_total / detection_confidence ebenso im frame_processor-Kontext
      - errors_total via metrics.record_error im frame_processor/call-sites
      - active_cameras: wird in der Regel im Router inkrementiert; optional hier im finally dekrementieren,
        wenn du es zentral haben willst.
    """
    current = threading.current_thread()
    current.name = thread_name

    cap = cv2.VideoCapture(stream_url)
    video_captures[camera_id] = cap

    if not cap.isOpened():
        metrics.record_error(str(camera_id), "OpenCaptureError", "camera_worker_init")
        # Falls du active_cameras im Router inkrementierst, hier optional dekrementieren, wenn Start scheitert
        metrics.active_cameras.dec()
        camera_running[camera_id] = False
        return

    try:
        while camera_running.get(camera_id, False):
            ok, frame = cap.read()
            if not ok:
                # Kein Frame – nicht hart abbrechen, kurz weiterprobieren
                continue

            try:
                res = adapter.predict(frame)  # generisch
                events = []

                # process_frame misst Latenz selbst via metrics.measure_latency(...)
                for out in process_frame(frame, res.raw, camera_id, model_task):
                    if "class_name" in out:
                        events.append(out["class_name"])
                    elif "frame" in out:
                        ok_jpg, buf = cv2.imencode(".jpg", out["frame"])
                        if ok_jpg:
                            set_latest(camera_id, buf.tobytes())

                if events:
                    db = SessionLocal()
                    try:
                        persisted_model_type = "objectDetection" if model_task == "detect" else model_task
                        for cls in events:
                            save_event(db, cls, persisted_model_type, camera_id)
                    finally:
                        db.close()

            except Exception as e:
                metrics.record_error(str(camera_id), type(e).__name__, "camera_frame_processing")
                # Schleife weiterlaufen lassen

    finally:
        try:
            cap.release()
        except Exception:
            pass
        # Wenn du active_cameras im Router inkrementierst, dekrementiere hier,
        # damit bei natürlichem Ende korrekt gezählt wird:
        metrics.active_cameras.dec()
        camera_running[camera_id] = False
