import cv2
import threading
from threading import Lock
from typing import Dict, Optional
import numpy as np  # optional für Platzhalter-Frame
from backend.monitoring.metrics import metrics

import numpy as np
import cv2

def set_placeholder_frame(camera_id: int, text: str = "Starting...", w: int = 320, h: int = 240):
    """Schreibt sofort ein schwarzes Platzhalter-JPEG. So liefert /process_frame/{id} direkt 200."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.putText(img, text, (10, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img)
    if ok:
        set_latest(camera_id, buf.tobytes())

# OpenCV-Captures pro Kamera
video_captures: Dict[int, cv2.VideoCapture] = {}
# Letztes JPEG pro Kamera
latest_frames: Dict[int, bytes] = {}
# Locks pro Kamera für Frames/State
frame_locks: Dict[int, Lock] = {}
# Worker-Threads
camera_threads: Dict[int, threading.Thread] = {}
# Laufstatus pro Kamera
camera_running: Dict[int, bool] = {}

# ----------------------- Helper / API für andere Module -----------------------

def is_running(camera_id: int) -> bool:
    """Gibt zurück, ob der Stream-Worker für diese Kamera läuft."""
    return bool(camera_running.get(camera_id, False))

def has_frame(camera_id: int) -> bool:
    """Ob bereits ein (irgendein) Frame vorliegt."""
    lock = frame_locks.get(camera_id)
    if not lock:
        return False
    with lock:
        return camera_id in latest_frames

def ensure_lock(camera_id: int) -> Lock:
    """Sorgt dafür, dass ein Lock existiert (idempotent)."""
    lock = frame_locks.get(camera_id)
    if lock is None:
        # atomar genug in unserem Kontext (einfacher Pfad)
        frame_locks[camera_id] = Lock()
        lock = frame_locks[camera_id]
    return lock

# ----------------------- Frame Zugriff -----------------------

def set_latest(camera_id: int, jpeg_bytes: bytes) -> None:
    """
    Setzt das neueste JPEG-Frame thread-sicher.
    Wird typischerweise vom Worker aufgerufen, nachdem ein Frame encodiert wurde.
    """
    lock = ensure_lock(camera_id)
    with lock:
        latest_frames[camera_id] = jpeg_bytes

def get_latest(camera_id: int) -> Optional[bytes]:
    """
    Gibt das neueste JPEG-Frame zurück oder None, wenn (noch) keins da ist.
    Thread-sicher und rennfest gegen paralleles cleanup().
    """
    lock = frame_locks.get(camera_id)
    if not lock:
        return None
    with lock:
        return latest_frames.get(camera_id)

# ----------------------- Optional: Warm-up Platzhalter -----------------------

def set_placeholder_frame(camera_id: int, width: int = 320, height: int = 240, text: str = "Starting...") -> None:
    """
    Legt ein schwarzes Platzhalter-JPEG ab, um 204 zu vermeiden (Optional).
    Kann direkt nach erfolgreichem Öffnen der Quelle vom Worker aufgerufen werden.
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    try:
        cv2.putText(img, text, (10, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
        ok, buf = cv2.imencode('.jpg', img)
        if ok:
            set_latest(camera_id, buf.tobytes())
    except Exception:
        # Platzhalter ist "nice to have" – stillschweigend ignorieren
        pass

# ----------------------- Cleanup -----------------------

def cleanup(camera_id: int, dec_metric: bool = True) -> None:
    """
    Räumt Ressourcen dieser Kamera auf.
    ACHTUNG: Nur HIER ODER im Worker 'finally' metrics.active_cameras.dec() ausführen – nicht beides!
    """
    # Capture schließen
    cap = video_captures.pop(camera_id, None)
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass

    # Thread/State/Frames/Locks entfernen
    thread = camera_threads.pop(camera_id, None)
    frame_locks.pop(camera_id, None)
    latest_frames.pop(camera_id, None)
    camera_running.pop(camera_id, None)

    # Metriken
    metrics.camera_status.labels(camera_id=str(camera_id), camera_name="").set(0)
    if dec_metric:
        metrics.active_cameras.dec()
