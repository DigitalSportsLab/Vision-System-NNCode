from fastapi import APIRouter, HTTPException
import threading
from pydantic import BaseModel

from backend.services.model_hub import resolve_key_from_legacy, load_adapter_by_key_safe
from backend.services.camera_manager import camera_threads, camera_running, frame_locks, cleanup
from backend.db_settings import SessionLocal
from backend.models import Camera
from backend.workers.camera_worker import run_camera_loop
from backend.monitoring.metrics import metrics

router = APIRouter()

class ModelRequest(BaseModel):
    model_type: str   # z.B. objectDetection | segmentation | pose | classification

def _resolve_stream_src(cam):
    """
    Liefert die richtige Quelle für OpenCV:
    - live:   int(Device-Index), z.B. "0" -> 0
    - andere: String (RTSP/HTTP/Datei) bleibt String
    """
    st = (cam.stream_type or "").lower()
    if st == "live":
        try:
            return int(str(cam.stream).strip())
        except Exception:
            return 0  # Fallback, falls DB-Wert leer/ungültig
    return cam.stream


@router.post("/start_camera_stream/{camera_id}")
def start_camera_stream(camera_id: int, req: ModelRequest):
    """Startet einen Live-Stream für eine einzelne Kamera (Registry → YOLO-Fallback)."""
    # Kamera holen
    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
    finally:
        db.close()

    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    if camera_running.get(camera_id):
        return {"message": "already running", "camera_id": camera_id}

    # Adapter laden (mit Fallback)
    try:
        key = resolve_key_from_legacy(req.model_type)
        adapter, resolved_key = load_adapter_by_key_safe(key, req.model_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model loading failed: {e}")

    # Ressourcen initialisieren
    frame_locks[camera_id] = threading.Lock()
    camera_running[camera_id] = True

    # aktive Kamera zählen (Worker dekrementiert beim Ende)
    metrics.active_cameras.inc()

    # Thread starten – wichtig: cam.stream verwenden
    src = _resolve_stream_src(cam)
    t = threading.Thread(
        target=run_camera_loop,
        args=(camera_id, src, adapter, adapter.task.value, f"🎥 {cam.source_name}"),
        daemon=True
    )
    t.start()
    camera_threads[camera_id] = t

    return {"message": f"Camera {camera_id} started", "model_key": resolved_key}

@router.post("/stop_camera_stream/{camera_id}")
def stop_camera_stream(camera_id: int):
    """Stoppt den Live-Stream einer Kamera und räumt auf."""
    if not camera_running.get(camera_id):
        return {"message": "not running", "camera_id": camera_id}

    camera_running[camera_id] = False
    t = camera_threads.get(camera_id)
    if t:
        t.join(timeout=2.0)

    cleanup(camera_id)
    # Hinweis: metrics.active_cameras.dec() macht der Worker im finally.
    return {"message": f"Camera {camera_id} stopped"}

@router.post("/start_webcam_stream")
def start_all_live_cameras(req: ModelRequest):
    """Startet alle Kameras mit stream_type == 'live' (Registry → YOLO-Fallback)."""
    # Adapter laden
    try:
        key = resolve_key_from_legacy(req.model_type)
        adapter, resolved_key = load_adapter_by_key_safe(key, req.model_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model loading failed: {e}")

    db = SessionLocal()
    try:
        live_cams = db.query(Camera).filter(Camera.stream_type == "live").all()
    finally:
        db.close()

    started = []
    for cam in live_cams:
        if camera_running.get(cam.id):
            continue
        frame_locks[cam.id] = threading.Lock()
        camera_running[cam.id] = True
        metrics.active_cameras.inc()

        src = _resolve_stream_src(cam)
        t = threading.Thread(
            target=run_camera_loop,
            args=(cam.id, src, adapter, adapter.task.value, f"🎥 {cam.source_name}"),
            daemon=True
        )
        t.start()
        camera_threads[cam.id] = t
        started.append(cam.id)

    return {"message": "Camera streams started", "model_key": resolved_key, "started": started}

@router.post("/stop_webcam_stream")
def stop_all_streams():
    """Stoppt alle laufenden Streams."""
    for cam_id, running in list(camera_running.items()):
        if not running:
            continue
        camera_running[cam_id] = False
        t = camera_threads.get(cam_id)
        if t:
            t.join(timeout=2.0)
        cleanup(cam_id)
    # dec() pro Kamera macht der Worker im finally.
    return {"message": "All camera streams stopped"}
