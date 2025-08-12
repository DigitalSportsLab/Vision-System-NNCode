import cv2, threading
from backend.services.frame_processor import process_frame
from backend.services.detection_service import save_event
from backend.services.camera_manager import video_captures, camera_running, set_latest
from backend.db_settings import SessionLocal
from backend.monitoring.metrics import metrics

def run_camera_loop(camera_id: int, stream_url: str, model, model_task: str, thread_name: str):
    current = threading.current_thread()
    current.name = thread_name

    cap = cv2.VideoCapture(stream_url)
    video_captures[camera_id] = cap

    try:
        while camera_running.get(camera_id, False):
            ok, frame = cap.read()
            if not ok: continue

            events = []
            for out in process_frame(frame, model(frame)[0], camera_id, model_task):
                if "class_name" in out: events.append(out["class_name"])
                elif "frame" in out:
                    _, buf = cv2.imencode(".jpg", out["frame"])
                    set_latest(camera_id, buf.tobytes())

            if events:
                db = SessionLocal()
                try:
                    for cls in events:
                        save_event(db, cls, model_task if model_task!="detect" else "objectDetection", camera_id)
                finally:
                    db.close()
    finally:
        cap.release()