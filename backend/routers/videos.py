import os, uuid, shutil
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Response
from pydantic import BaseModel
from backend.services.video_manager import (
    uploads_dir, video_threads, video_running, video_locks,
    get_latest, get_progress, get_error, cleanup, video_ctx_camera
)
from backend.services.yolo_service import YoloService
from backend.workers.video_worker import run_video_job
from backend.db_settings import SessionLocal
from backend.models import Camera
from backend.monitoring.metrics import metrics

import threading

router = APIRouter()

os.makedirs(uploads_dir, exist_ok=True)

class AnalyzeRequest(BaseModel):
    job_id: str
    model_type: str                 # objectDetection | segmentation | pose
    camera_id: Optional[int] = None # Kontextkamera

@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """Nimmt eine Videodatei entgegen und legt sie im uploads_dir ab. Gibt job_id + file_path zurück."""
    # einfache Validierung
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

@router.post("/videos/analyze")
async def analyze_video(req: AnalyzeRequest):
    """Startet die Analyse eines hochgeladenen Videos. Optional: Kamera als Kontext."""
    if req.model_type not in {"objectDetection", "segmentation", "pose"}:
        raise HTTPException(400, "Invalid model_type")

    # datei prüfen
    # Wir konstruieren den erwarteten Dateinamen wie in upload
    # Alternativ könntest du den file_path vom Upload mitgeben.
    prefix = os.path.join(uploads_dir, f"{req.job_id}_")
    candidates = [os.path.join(uploads_dir, f) for f in os.listdir(uploads_dir) if f.startswith(f"{req.job_id}_")]
    if not candidates:
        raise HTTPException(404, "Uploaded file not found for job_id")
    file_path = candidates[0]

    # optionale kamera prüfen
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

    # YOLO laden
    weights = {
        "objectDetection": "yolov8s.pt",
        "segmentation": "yolov8n-seg.pt",
        "pose": "yolov8n-pose.pt"
    }[req.model_type]
    model = YoloService.get(
        "detect" if req.model_type=="objectDetection" else ("segment" if req.model_type=="segmentation" else "pose"),
        weights
    )

    if req.job_id in video_running and video_running[req.job_id]:
        return {"message": "Job already running", "job_id": req.job_id}

    # Job-State initialisieren
    video_locks[req.job_id] = threading.Lock()
    video_running[req.job_id] = True
    video_ctx_camera[req.job_id] = cam_id

    # Metriken: aktiven Video-Job zählen
    metrics.active_video_jobs.inc()

    # Thread starten
    t = threading.Thread(
        target=run_video_job,
        args=(req.job_id, file_path, model, model.task, cam_id),
        daemon=True
    )
    t.start()
    video_threads[req.job_id] = t

    return {"message": "Analysis started", "job_id": req.job_id, "model_type": req.model_type, "camera_id": cam_id}

@router.get("/videos/{job_id}/status")
async def video_status(job_id: str):
    """Status/Progress + evtl. Fehler"""
    return {
        "job_id": job_id,
        "running": bool(video_running.get(job_id, False)),
        "progress": get_progress(job_id),
        "error": get_error(job_id),
        "camera_id": video_ctx_camera.get(job_id)
    }

@router.get("/videos/{job_id}/frame")
async def video_latest_frame(job_id: str):
    """Letztes verarbeitetes Frame als JPEG (wie bei Live-Streams)."""
    data = get_latest(job_id)
    if data is None:
        raise HTTPException(404, "No frame available yet")
    return Response(content=data, media_type="image/jpeg")

@router.post("/videos/{job_id}/stop")
async def stop_video(job_id: str):
    """Stoppt einen laufenden Job und räumt auf."""
    if job_id in video_running:
        video_running[job_id] = False
        t = video_threads.get(job_id)
        if t:
            t.join(timeout=2.0)
        cleanup(job_id)

    return {"message": "stopped", "job_id": job_id}
