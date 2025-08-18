from typing import List, Optional
from datetime import timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.db_settings import SessionLocal
from backend.models import DetectionEvent, Camera

router = APIRouter()

# DB-Session Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DetectionOut(BaseModel):
    id: int
    class_name: str
    model_type: str
    camera_id: int
    camera_name: Optional[str] = None
    timestamp: Optional[str] = None  # JS-freundlicher ISO-String, z. B. 2025-08-13T12:34:56.123Z

    @classmethod
    def from_row(cls, row: DetectionEvent, cam_name: Optional[str] = None):
        ts = getattr(row, "timestamp", None)

        # Alte, naive Datumswerte (von utcnow) als UTC interpretieren
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        iso = None
        if ts is not None:
            # ISO 8601 mit Millisekunden
            iso = ts.isoformat(timespec="milliseconds")
            # "+00:00" -> "Z" für sauberes UTC
            if iso.endswith("+00:00"):
                iso = iso[:-6] + "Z"

        return cls(
            id=row.id,
            class_name=row.class_name,
            model_type=row.model_type,
            camera_id=row.camera_id,
            camera_name=cam_name,
            timestamp=iso,
        )


@router.get("/detection", response_model=List[DetectionOut])
async def list_detections(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    model: Optional[str] = Query(None, description="z.B. objectDetection | segmentation | pose | all"),
    camera_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(DetectionEvent)
    if model and model != "all":
        q = q.filter(DetectionEvent.model_type == model)
    if camera_id is not None:
        q = q.filter(DetectionEvent.camera_id == camera_id)

    rows = (
        q.order_by(desc(DetectionEvent.timestamp))
         .offset(offset)
         .limit(limit)
         .all()
    )

    # Kameranamen bulk-laden
    cam_ids = {r.camera_id for r in rows}
    cam_map = {}
    if cam_ids:
        cams = db.query(Camera).filter(Camera.id.in_(cam_ids)).all()
        cam_map = {c.id: getattr(c, "source_name", None) for c in cams}

    return [DetectionOut.from_row(r, cam_map.get(r.camera_id)) for r in rows]
