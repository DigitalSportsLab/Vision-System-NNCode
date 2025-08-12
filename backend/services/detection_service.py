from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import DetectionEvent, Camera

def save_event(db: Session, class_name: str, model_type: str, camera_id: int):
    cam = db.query(Camera).filter(Camera.id==camera_id).first()
    ev = DetectionEvent(
        class_name=class_name,
        model_type=model_type,
        camera_id=camera_id,
        camera_name=cam.source_name if cam else f"Camera {camera_id}",
        timestamp=datetime.utcnow()
    )
    db.add(ev)
    db.commit()
