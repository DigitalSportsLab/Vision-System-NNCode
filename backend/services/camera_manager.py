import cv2, threading
from threading import Lock
from typing import Dict
from backend.monitoring.metrics import metrics

video_captures: Dict[int, cv2.VideoCapture] = {}
latest_frames: Dict[int, bytes] = {}
frame_locks: Dict[int, Lock] = {}
camera_threads: Dict[int, threading.Thread] = {}
camera_running: Dict[int, bool] = {}

def set_latest(camera_id: int, jpeg_bytes: bytes):
    with frame_locks[camera_id]:
        latest_frames[camera_id] = jpeg_bytes

def get_latest(camera_id: int) -> bytes | None:
    lock = frame_locks.get(camera_id)
    if lock is None or camera_id not in latest_frames:
        return None
    with lock:
        return latest_frames[camera_id]

def cleanup(camera_id: int):
    cap = video_captures.pop(camera_id, None)
    if cap: cap.release()
    frame_locks.pop(camera_id, None)
    latest_frames.pop(camera_id, None)
    camera_threads.pop(camera_id, None)
    camera_running.pop(camera_id, None)
    metrics.camera_status.labels(camera_id=str(camera_id), camera_name="").set(0)
    metrics.active_cameras.dec()
