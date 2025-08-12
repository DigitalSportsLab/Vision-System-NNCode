from fastapi import APIRouter, HTTPException, Response
from backend.services.camera_manager import get_latest

router = APIRouter()

@router.get("/process_frame/{camera_id}")
def process_frame_endpoint(camera_id: int):
    data = get_latest(camera_id)
    if data is None:
        raise HTTPException(404, "No frame available")
    return Response(content=data, media_type="image/jpeg")
