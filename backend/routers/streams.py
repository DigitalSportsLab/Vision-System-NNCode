from fastapi import APIRouter, HTTPException
import threading
from pydantic import BaseModel
from backend.services.yolo_service import YoloService
from backend.services.camera_manager import camera_threads, camera_running, frame_locks, cleanup
from backend.db_settings import SessionLocal
from backend.models import Camera
from backend.core.settings import settings
from backend.workers.camera_worker import run_camera_loop

router = APIRouter()

class ModelRequest(BaseModel):
    model_type: str  # "objectDetection" | "segmentation" | "pose"

def _weights_for(t: str):
    from backend.core.settings import settings
    return {
        "objectDetection": settings.YOLO_DETECT,
        "segmentation": settings.YOLO_SEG,
        "pose": settings.YOLO_POSE
    }[t]

@router.post("/start_camera_stream/{camera_id}")
def start_camera_stream(camera_id: int, req: ModelRequest):
    if req.model_type not in {"objectDetection","segmentation","pose"}:
        raise HTTPException(400, "Invalid model selected")

    # Kamera holen
    db = SessionLocal(); cam = db.query(Camera).filter(Camera.id==camera_id).first(); db.close()
    if not cam: raise HTTPException(404,"Camera not found")

    if camera_running.get(camera_id): return {"message":"already running"}

    weights = _weights_for(req.model_type)
    model = YoloService.get(
        "detect" if req.model_type=="objectDetection" else ("segment" if req.model_type=="segmentation" else "pose"),
        weights
    )

    frame_locks[camera_id] = threading.Lock()
    camera_running[camera_id] = True

    t = threading.Thread(
        target=run_camera_loop,
        args=(camera_id, cam.stream, model, model.task, f"🎥 {cam.source_name}"),
        daemon=True
    )
    t.start()
    camera_threads[camera_id] = t
    return {"message": f"Camera {camera_id} started", "model_type": req.model_type}

@router.post("/stop_camera_stream/{camera_id}")
def stop_camera_stream(camera_id: int):
    if not camera_running.get(camera_id): return {"message":"not running"}
    camera_running[camera_id] = False
    t = camera_threads.get(camera_id)
    if t: t.join(timeout=2.0)
    cleanup(camera_id)
    return {"message": f"Camera {camera_id} stopped"}
