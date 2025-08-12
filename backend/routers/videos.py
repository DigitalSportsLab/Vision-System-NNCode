import os, uuid, shutil, threading
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Response, status
from pydantic import BaseModel

from backend.services.video_manager import (
    uploads_dir, video_threads, video_running, video_locks,
    get_latest, get_progress, get_error, cleanup, video_ctx_camera
)
from backend.services.model_hub import resolve_key_from_legacy, load_adapter_by_key_safe
from backend.workers.video_worker import run_video_job
from backend.db_settings import SessionLocal
from backend.models import Camera
from backend.monitoring.metrics import metrics

router = APIRouter()

os.makedirs(uploads_dir, exist_ok=True)

class AnalyzeRequest(BaseModel):
    job_id: str
    model_type: str                 # z.B. objectDetection | segmentation | pose | classification
    camera_id: Optional[int] = None # Kontextkamera (optional)

@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """Speichert die Datei im uploads_dir und gibt job_id + path zurück."""
    if not file.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    job_id = str(uuid.uuid4())
    dest_path = os.path.join(uploads_dir, f"{job_id}_{file.filename}")

    try:
        with open(dest_path, "wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    return {"job_id": job_id, "file_path": dest_path}

@router.post("/videos/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_video(req: AnalyzeRequest):
    """Startet die Analyse des hochgeladenen Videos. Nutzt Registry → YOLO-Fallback bei Bedarf."""
    # Datei finden
    candidates = [os.path.join(uploads_dir, f) for f in os.listdir(uploads_dir) if f.startswith(f"{req.job_id}_")]
    if not candidates:
        raise HTTPException(404, "Uploaded file not found for job_id")
    file_path = candidates[0]

    # Kamera-Kontext prüfen (optional)
    cam_id: int | None = None
    if req.camera_id is not None:
        db = SessionLocal()
        try:
            cam = db.query(Camera).filter(Camera.id == req.camera_id).first()
            if not cam:
                raise HTTPException(404, "Camera not found")
            cam_id = cam.id
        finally:
            db.close()

    # Adapter über Registry laden — mit automatischem YOLO-Fallback
    try:
        key = resolve_key_from_legacy(req.model_type)            # z.B. "yolo/v8s:detect"
        adapter, resolved_key = load_adapter_by_key_safe(key, req.model_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model resolution/loading failed: {e}")

    # Job bereits aktiv?
    if req.job_id in video_running and video_running[req.job_id]:
        return {"message": "Job already running", "job_id": req.job_id, "model_key": resolved_key}

    # Job-Status initialisieren
    video_locks[req.job_id] = threading.Lock()
    video_running[req.job_id] = True
    video_ctx_camera[req.job_id] = cam_id

    # Metrik: aktiven Video-Job zählen (der Worker dekrementiert beim Ende)
    metrics.active_video_jobs.inc()

    # Thread starten
    t = threading.Thread(
        target=run_video_job,
        args=(req.job_id, file_path, adapter, adapter.task.value, cam_id),
        daemon=True
    )
    t.start()
    video_threads[req.job_id] = t

    return {
        "message": "Analysis started",
        "job_id": req.job_id,
        "model_key": resolved_key,   # zeigt ggf. den Fallback-Key (z. B. "yolo/v8s:detect")
        "camera_id": cam_id
    }

@router.get("/videos/{job_id}/status")
async def video_status(job_id: str):
    """Status/Progress und evtl. Fehlermeldung zum Job."""
    return {
        "job_id": job_id,
        "running": bool(video_running.get(job_id, False)),
        "progress": get_progress(job_id),
        "error": get_error(job_id),
        "camera_id": video_ctx_camera.get(job_id)
    }

@router.get("/videos/{job_id}/frame")
async def video_latest_frame(job_id: str):
    """Letztes verarbeitetes, annotiertes Frame als JPEG."""
    data = get_latest(job_id)
    if data is None:
        raise HTTPException(404, "No frame available yet")
    return Response(content=data, media_type="image/jpeg")

@router.post("/videos/{job_id}/stop")
async def stop_video(job_id: str):
    """Stoppt einen laufenden Video-Job und räumt auf."""
    if job_id in video_running:
        video_running[job_id] = False
        t = video_threads.get(job_id)
        if t:
            t.join(timeout=2.0)
        cleanup(job_id)
    return {"message": "stopped", "job_id": job_id}
