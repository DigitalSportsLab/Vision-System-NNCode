import threading
from threading import Lock
from typing import Dict, Optional

uploads_dir = "data/uploads"  # kannst du per Settings steuern

video_threads: Dict[str, threading.Thread] = {}
video_running: Dict[str, bool] = {}
video_locks: Dict[str, Lock] = {}
video_latest_frames: Dict[str, bytes] = {}
video_progress: Dict[str, float] = {}          # 0.0..100.0
video_errors: Dict[str, str] = {}
video_ctx_camera: Dict[str, Optional[int]] = {} # job_id -> camera_id

def set_latest(job_id: str, jpeg_bytes: bytes):
    with video_locks[job_id]:
        video_latest_frames[job_id] = jpeg_bytes

def get_latest(job_id: str) -> Optional[bytes]:
    lock = video_locks.get(job_id)
    if lock is None or job_id not in video_latest_frames:
        return None
    with lock:
        return video_latest_frames[job_id]

def set_progress(job_id: str, pct: float):
    video_progress[job_id] = max(0.0, min(100.0, pct))

def get_progress(job_id: str) -> float:
    return video_progress.get(job_id, 0.0)

def set_error(job_id: str, msg: str):
    video_errors[job_id] = msg

def get_error(job_id: str) -> Optional[str]:
    return video_errors.get(job_id)

def cleanup(job_id: str):
    video_threads.pop(job_id, None)
    video_running.pop(job_id, None)
    video_locks.pop(job_id, None)
    video_latest_frames.pop(job_id, None)
    video_progress.pop(job_id, None)
    video_errors.pop(job_id, None)
    video_ctx_camera.pop(job_id, None)
