from typing import Any, Dict, Optional, List
from datetime import datetime
import json
import requests

from fastapi import APIRouter, HTTPException, Body, status
from sqlalchemy.orm import Session

from backend.db_settings import SessionLocal
from backend.models import Camera

router = APIRouter()

@router.get("/cameras")
def get_cameras():
    db: Session = SessionLocal()
    try:
        cameras: List[Camera] = db.query(Camera).all()
        camera_list = []
        for camera in cameras:
            camera_list.append({
                "id": camera.id,
                "source_name": camera.source_name,
                "stream_type": camera.stream_type,
                "stream": camera.stream,
                "location": camera.location,
                "created_at": camera.created_at.strftime("%Y-%m-%d %H:%M:%S") if camera.created_at else None
            })
        return camera_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cameras: {str(e)}"
        )
    finally:
        db.close()


@router.post("/cameras")
def add_camera(camera: dict):
    """
    1:1 wie im Original: proxyt auf den internen Endpoint /api/create_camera.
    (In der Praxis würdest du direkt create_camera aufrufen.)
    """
    api_url = "http://localhost:8000/api/create_camera"
    try:
        response = requests.post(api_url, json=camera, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Proxy to create_camera failed: {e}")


@router.post("/create_camera")
async def create_camera(
    camera_data: Dict[str, Any] = Body(..., example={
        "source_name": "Camera 1",
        "stream_type": "RTSP",
        "stream": "rtsp://example.com/stream",
        "location": "Main Entrance"
    })
):
    """Create a new camera entry in the database (direkt, ohne Proxy)."""
    db: Session = SessionLocal()
    try:
        db_camera = Camera(
            source_name=camera_data["source_name"],
            stream_type=camera_data["stream_type"],
            stream=camera_data["stream"],
            location=camera_data.get("location"),
        )
        db.add(db_camera)
        db.commit()
        db.refresh(db_camera)

        return {
            "source_name": db_camera.source_name,
            "stream_type": db_camera.stream_type,
            "stream": db_camera.stream,
            "location": db_camera.location,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating camera: {str(e)}"
        )
    finally:
        db.close()


@router.delete("/cameras/{camera_id}")
async def delete_camera(camera_id: int):
    """Delete a camera from the database"""
    db: Session = SessionLocal()
    try:
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        db.delete(camera)
        db.commit()
        return {"message": f"Camera {camera_id} deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting camera: {str(e)}"
        )
    finally:
        db.close()
