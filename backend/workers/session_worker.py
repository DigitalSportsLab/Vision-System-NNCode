# backend/services/session_worker.py
import threading
import cv2
import time
from collections import defaultdict

# einfacher Speicher für die letzten Frames (per camera_id)
_latest_frames = {}
_running = {}
_threads = {}

def camera_loop(camera_id: int, stream_url: str):
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print(f"[Worker] Camera {camera_id}: could not open stream {stream_url}")
        return
    
    _running[camera_id] = True
    while _running.get(camera_id, False):
        ret, frame = cap.read()
        if not ret:
            continue
        # hier könnten wir Pipeline/Inferenz anhängen
        _latest_frames[camera_id] = frame
        time.sleep(0.03)  # ~30 fps
    cap.release()
    print(f"[Worker] Camera {camera_id} stopped.")

def start_session_worker(camera_id: int, stream_url: str):
    if camera_id in _threads and _threads[camera_id].is_alive():
        return {"message": "Already running"}
    t = threading.Thread(target=camera_loop, args=(camera_id, stream_url), daemon=True)
    _threads[camera_id] = t
    t.start()
    return {"message": f"Started worker for camera {camera_id}"}

def terminate_session_worker(camera_id: int):
    _running[camera_id] = False
    return {"message": f"Stopping worker for camera {camera_id}"}

def get_latest_frame(camera_id: int):
    return _latest_frames.get(camera_id)
