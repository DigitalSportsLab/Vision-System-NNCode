# backend/routers/compat_live.py
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session as OrmSession
from backend.db_settings import SessionLocal
from backend.models import Camera
from backend.workers.session_worker import start_session_worker, terminate_session_worker, get_latest_frame
import cv2

router = APIRouter(tags=["compat-live"])

@router.get("/api/cameras")
def api_cameras():
    """Alias für Frontend: liefert Kamera-Liste mit stream_type/live-Flag."""
    db: OrmSession = SessionLocal()
    try:
        cams = db.query(Camera).all()
        # Output so formen, wie dein Frontend es erwartet
        out = []
        for c in cams:
            out.append({
                "id": c.id,
                "source_name": c.source_name,
                "stream_type": c.stream_type or "live",  # default "live"
                "stream": c.stream,
                "location": c.location,
            })
        return out
    finally:
        db.close()


@router.post("/start_camera_stream/{camera_id}")
def start_camera_stream(camera_id: int, model_type: str | None = None):
    db: OrmSession = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")
        return start_session_worker(camera_id, cam.stream)
    finally:
        db.close()

@router.post("/stop_camera_stream/{camera_id}")
def stop_camera_stream(camera_id: int):
    return terminate_session_worker(camera_id)

@router.get("/process_frame/{camera_id}")
def process_frame(camera_id: int):
    frame = get_latest_frame(camera_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame available")
    ok, jpg = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Encoding failed")
    return Response(content=jpg.tobytes(), media_type="image/jpeg")
