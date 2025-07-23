import numpy as np
import threading
from queue import Queue, Empty
import time
from pydantic import BaseModel
from dataclasses import Field, dataclass
from typing import Dict, List, Optional, Any
import cv2
from ultralytics import YOLO
from datetime import datetime, timedelta
from collections import defaultdict
import requests
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from fastapi import FastAPI, File, HTTPException, UploadFile, Response, Body, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import io
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from threading import Lock
from logging.handlers import RotatingFileHandler
from prometheus_fastapi_instrumentator import Instrumentator

from backend import schemas  # Import logging
from .db_settings import init_db, SessionLocal  # Import SessionLocal from db_settings
from .models import DetectionEvent, Camera
from backend import models  # Add this import
from .monitoring.metrics import metrics

# Create custom loggers
app_logger = logging.getLogger('app')
fastapi_logger = logging.getLogger('uvicorn.access')
yolo_logger = logging.getLogger('ultralytics')

# Configure app logger
app_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(threadName)s - %(message)s', 
                            datefmt='%H:%M:%S')

# Console handler with custom formatting
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
app_logger.addHandler(console_handler)

# Suppress other loggers
fastapi_logger.handlers = []
yolo_logger.handlers = []

# Create the FastAPI app
app = FastAPI()

# Add Prometheus instrumentation BEFORE any other setup
Instrumentator().instrument(app).expose(app)

# Allow CORS for React frontend
# Get CORS origins from environment variable
cors_origins = os.getenv("CORS_ORIGINS", '["*"]')
try:
    # Parse the JSON string to get the list of origins
    allowed_origins = json.loads(cors_origins)
except json.JSONDecodeError:
    # Fallback to allowing all origins if parsing fails
    allowed_origins = ["*"]
    app_logger.warning("Failed to parse CORS_ORIGINS, falling back to allow all origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
video_captures = {}  # Dictionary to store VideoCapture objects for each camera
latest_frames = {}   # Dictionary to store latest frames for each camera
active_streams = {}
fps_stats = {}
sources = []
cameras = []
recent_alerts = []
alert_queue = Queue()
model = None # Load the YOLO model

# Global variable for webcam control
cap = None
latest_frame = None
running = False

# Replace the global detection_times with a nested dictionary
detection_times = defaultdict(lambda: defaultdict(lambda: datetime.min))

# Replace the global variable with a dictionary to track per-camera detections
detected_objects_this_session = {}  # Changed from set() to dict()

# Add these at the top with other global variables
camera_threads = {}  # Store threads for each camera
camera_running = {}  # Track running state for each camera
frame_locks = {}    # Locks for thread-safe frame access

def fetch_cameras():
    """Fetch all cameras from the API"""
    try:
        response = requests.get("http://localhost:8000/api/cameras")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch cameras: {response.status_code}")
            return []
    except requests.exceptions.ConnectionError:
        print("Could not connect to API server")
        return []
    except Exception as e:
        print(f"Error fetching cameras: {str(e)}")
        return []


def process_frame(frame, result, camera_id):
    """Process a single frame and apply detections based on model type."""
    with metrics.measure_latency(str(camera_id), model.task):
        try:
            annotated_frame = frame.copy()
            alert = None

            # Initialize camera's detection set if not exists
            if camera_id not in detected_objects_this_session:
                detected_objects_this_session[camera_id] = set()

            # Define color constants
            KEYPOINT_COLOR = (0, 255, 0)  # Green
            SKELETON_COLOR = (0, 255, 255)  # Yellow
            DETECTION_COLORS = {
                "person": (0, 0, 255),    # Red
                "bottle": (0, 255, 0),    # Green
                "potted plant": (255, 0, 0)  # Blue
            }

            try:
                # Handle pose estimation
                if hasattr(result, 'keypoints') and result.keypoints is not None:
                    for person in result.keypoints:
                        keypoints = person.data[0].cpu().numpy()
                        
                        # Draw keypoints
                        for kp in keypoints:
                            if kp[2] > 0.5:  # Confidence threshold
                                x, y = int(kp[0]), int(kp[1])
                                cv2.circle(annotated_frame, (x, y), 4, KEYPOINT_COLOR, -1)
                        
                        # Define skeleton connections (COCO format)
                        skeleton = [
                            [16,14], [14,12], [17,15], [15,13], [12,13], [6,12], [7,13],
                            [6,7], [6,8], [7,9], [8,10], [9,11], [2,3], [1,2], [1,3],
                            [2,4], [3,5], [4,6], [5,7]
                        ]
                        
                        # Draw skeleton
                        for connection in skeleton:
                            start_idx = connection[0] - 1
                            end_idx = connection[1] - 1
                            
                            if (keypoints[start_idx][2] > 0.5 and 
                                keypoints[end_idx][2] > 0.5):
                                
                                start_point = (int(keypoints[start_idx][0]), 
                                     int(keypoints[start_idx][1]))
                                end_point = (int(keypoints[end_idx][0]), 
                                   int(keypoints[end_idx][1]))
                                
                                cv2.line(annotated_frame, start_point, end_point, 
                                        SKELETON_COLOR, 2)

                # Handle segmentation
                if hasattr(result, 'masks') and result.masks is not None:
                    for i, mask in enumerate(result.masks):
                        try:
                            class_id = int(result.boxes[i].cls[0])
                            class_name = result.names[class_id]
                            
                            if class_name in DETECTION_COLORS:
                                mask_array = mask.data.cpu().numpy()[0]
                                
                                # Resize mask if needed
                                if mask_array.shape[:2] != frame.shape[:2]:
                                    mask_array = cv2.resize(
                                        mask_array,
                                        (frame.shape[1], frame.shape[0]),
                                        interpolation=cv2.INTER_NEAREST
                                    )
                                
                                # Create and apply mask overlay
                                binary_mask = (mask_array > 0.5).astype(np.uint8)
                                color = DETECTION_COLORS[class_name]
                                mask_overlay = np.zeros_like(frame)
                                mask_overlay[binary_mask == 1] = color
                                
                                # Blend with original frame
                                mask_area = (binary_mask > 0)
                                annotated_frame[mask_area] = cv2.addWeighted(
                                    annotated_frame[mask_area],
                                    0.6,  # Original frame weight
                                    mask_overlay[mask_area],
                                    0.4,  # Mask weight
                                    0
                                )
                                
                        except Exception as e:
                            logging.error(f"Error processing mask {i}: {str(e)}")
                            continue

                # Handle object detection boxes
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        try:
                            # Get box information
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            class_id = int(box.cls[0])
                            confidence = float(box.conf[0])
                            class_name = result.names[class_id]

                            if class_name in DETECTION_COLORS:
                                color = DETECTION_COLORS[class_name]
                                
                                # Draw bounding box
                                cv2.rectangle(
                                    annotated_frame,
                                    (int(x1), int(y1)),
                                    (int(x2), int(y2)),
                                    color,
                                    2
                                )
                                
                                # Add label
                                label = f"{class_name} {confidence:.2f}"
                                label_size, baseline = cv2.getTextSize(
                                    label,
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    2
                                )
                                
                                # Draw label background
                                label_y = max(y1 - 10, label_size[1])
                                cv2.rectangle(
                                    annotated_frame,
                                    (int(x1), int(label_y - label_size[1])),
                                    (int(x1 + label_size[0]), int(label_y + baseline)),
                                    color,
                                    cv2.FILLED
                                )
                                
                                # Draw label text
                                cv2.putText(
                                    annotated_frame,
                                    label,
                                    (int(x1), int(label_y)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (255, 255, 255),
                                    2
                                )
                                
                        except Exception as e:
                            logging.error(f"Error processing box: {str(e)}")
                            continue

                # Add frame metadata
                cv2.putText(
                    annotated_frame,
                    f"Frame Size: {frame.shape[1]}x{frame.shape[0]}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )

                # Modified detection tracking logic
                for box in result.boxes:
                    class_name = result.names[int(box.cls[0])]
                    valid_detection = (
                        class_name == "person" or 
                        (class_name == "bottle" and model.task == "detect")
                    )
                    
                    if valid_detection and class_name not in detected_objects_this_session[camera_id]:
                        current_time = datetime.now()
                        if detection_times[camera_id][class_name] == datetime.min:
                            detection_times[camera_id][class_name] = current_time
                        elif current_time - detection_times[camera_id][class_name] >= timedelta(seconds=10):
                            model_type = "objectDetection" if model.task == "detect" else (
                                "segmentation" if model.task == "segment" else "pose"
                            )
                            save_event_to_db(class_name, model_type, camera_id)
                            detected_objects_this_session[camera_id].add(class_name)
                            detection_times[camera_id][class_name] = datetime.min

                if valid_detection:
                    metrics.record_detection(
                        camera_id=str(camera_id),
                        class_name=class_name,
                        model_type=model.task,
                        confidence=confidence
                    )

            except Exception as e:
                logging.error(f"Error in process_frame: {str(e)}")
                return frame, None  # Return original frame on error

            return annotated_frame, alert

        except Exception as e:
            metrics.record_error(
                camera_id=str(camera_id),
                error_type=type(e).__name__,
                component="frame_processing"
            )
            return frame, None

def capture_frames_for_camera(camera_id):
    """Capture and process frames for a single camera"""
    # Get camera name from database
    db = SessionLocal()
    try:
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        camera_name = camera.source_name if camera else f"Camera {camera_id}"
    finally:
        db.close()

    current_thread = threading.current_thread()
    current_thread.name = f"🎥 {camera_name}"  # Use actual camera name
    
    thread_info = {
        "camera_id": camera_id,
        "camera_name": camera_name,
        "thread_name": current_thread.name,
        "thread_id": current_thread.ident,
        "start_time": datetime.now().strftime("%H:%M:%S")
    }
    
    # Use custom logger with camera name
    app_logger.info("╔════════════════════════════════════")
    app_logger.info(f"║ {camera_name} Thread Started")
    app_logger.info(f"║ Thread Name: {current_thread.name}")
    app_logger.info(f"║ Thread ID: {current_thread.ident}")
    app_logger.info("╚════════════════════════════════════")
    
    if not hasattr(app, 'camera_threads_info'):
        app.camera_threads_info = {}
    app.camera_threads_info[camera_id] = thread_info
    
    try:
        cap = video_captures[camera_id]
        while camera_running.get(camera_id, False):
            ret, frame = cap.read()
            if not ret:
                logging.error(f"Failed to read frame from camera {camera_id}")
                continue

            try:
                results = model(frame)
                annotated_frame, alert = process_frame(frame, results[0], camera_id)
                
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                with frame_locks[camera_id]:
                    latest_frames[camera_id] = buffer.tobytes()
            except Exception as e:
                logging.error(f"Error processing frame for camera {camera_id}: {str(e)}")
                continue

    except Exception as e:
        logging.error(f"Error in capture_frames for {camera_name}: {str(e)}")
    finally:
        if hasattr(app, 'camera_threads_info') and camera_id in app.camera_threads_info:
            del app.camera_threads_info[camera_id]

@app.get("/api/cameras")
def get_cameras():
    db = SessionLocal()
    try:
        cameras = db.query(Camera).all()
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
        print(f"Error fetching cameras: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cameras: {str(e)}"
        )
    finally:
        db.close()

@app.post("/api/cameras")
def add_camera(camera: dict):
    """Create a new camera entry"""
    api_url = "http://localhost:8000/api/create_camera"
    response = requests.post(api_url, json=camera)
    return response.json()

@app.get("/api/alerts")
def get_alerts():
    """Fetch recent alerts"""
    return recent_alerts


class ModelRequest(BaseModel):
    model_type: str

@app.post("/start_webcam_stream")
async def start_webcam_stream(request: ModelRequest):
    """Start webcam streams with separate thread per camera."""
    global model, detected_objects_this_session
    
    try:
        # Set up model based on request
        if request.model_type == 'objectDetection':
            model = YOLO('yolov8s.pt')
        elif request.model_type == 'segmentation':
            model = YOLO('yolov8n-seg.pt')
        elif request.model_type == 'pose':
            model = YOLO('yolov8n-pose.pt')
        else:
            raise HTTPException(status_code=400, detail="Invalid model selected")

        # Get all live cameras
        db = SessionLocal()
        live_cameras = db.query(Camera).filter(Camera.stream_type == 'live').all()
        db.close()

        detected_objects_this_session.clear()

        # Start a thread for each camera
        app_logger.info("╔═══════════════════════════════")
        app_logger.info("║ Starting Camera Streams")
        app_logger.info("╚═══════════════════════════════")
        
        for camera in live_cameras:
            if camera.id not in camera_threads or not camera_threads[camera.id].is_alive():
                # Initialize camera resources
                video_captures[camera.id] = cv2.VideoCapture(0)  # or camera.stream for RTSP
                frame_locks[camera.id] = Lock()
                camera_running[camera.id] = True
                detected_objects_this_session[camera.id] = set()
                
                # Create and start thread for this camera
                thread = threading.Thread(
                    target=capture_frames_for_camera,
                    args=(camera.id,),
                    daemon=True
                )
                thread.start()
                camera_threads[camera.id] = thread
                
                app_logger.info(f"► Initializing Camera {camera.id}")
                
        return {"message": "Camera streams started", "model_type": request.model_type}
    
    except Exception as e:
        app_logger.error(f"Error starting streams: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop_webcam_stream")
async def stop_webcam_stream():
    """Stop all camera streams."""
    try:
        app_logger.info("╔═══════════════════════════════")
        app_logger.info("║ 🛑 Stopping Camera Streams")
        app_logger.info("╚═══════════════════════════════")
        
        # Signal all threads to stop
        for camera_id in list(camera_running.keys()):
            camera_running[camera_id] = False
            
            # Wait for thread to finish
            if camera_id in camera_threads:
                thread = camera_threads[camera_id]
                thread.join(timeout=2.0)
                
                if not thread.is_alive():
                    app_logger.info(f"🎥 Camera {camera_id} - Thread stopped")
                    
                    # Clean up resources
                    if camera_id in video_captures:
                        video_captures[camera_id].release()
                        del video_captures[camera_id]
                        del frame_locks[camera_id]
                        del latest_frames[camera_id]
                        del camera_threads[camera_id]
                        del camera_running[camera_id]

        return {"message": "Camera streams stopped"}
    
    except Exception as e:
        app_logger.error(f"💥 Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/process_frame/{camera_id}")
async def process_frame_endpoint(camera_id: int):
    """Return the latest processed frame for a specific camera."""
    if camera_id not in latest_frames:
        raise HTTPException(status_code=404, detail="No frame available for this camera")
    
    try:
        with frame_locks.get(camera_id, Lock()):
            frame_data = latest_frames[camera_id]
        return Response(content=frame_data, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
def shutdown_event():
    """Release the webcam when the application shuts down."""
    if cap is not None:
        cap.release()

def save_event_to_db(class_name, model_type, camera_id):
    """Save detection event to database with error handling"""
    db = SessionLocal()
    try:
        # Get camera info
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        camera_name = camera.source_name if camera else f"Camera {camera_id}"
        
        event = DetectionEvent(
            class_name=class_name,
            model_type=model_type,
            camera_id=camera_id,
            camera_name=camera_name,
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
        logging.info(f"Successfully saved event: {class_name} from {camera_name}")
    except Exception as e:
        logging.error(f"Error saving event to database: {str(e)}")
        db.rollback()
    finally:
        db.close()

@app.post("/api/create_camera")
async def create_camera(
    camera_data: Dict[str, Any] = Body(..., example={
        "source_name": "Camera 1",
        "stream_type": "RTSP",
        "stream": "rtsp://example.com/stream",
        "location": "Main Entrance"
    })
):
    """Create a new camera entry in the database"""
    db = SessionLocal()
    try:
        # Debug prints
        print("Received camera data:", camera_data)
        
        # Create new Camera instance
        db_camera = Camera(
            source_name=camera_data['source_name'],
            stream_type=camera_data['stream_type'],
            stream=camera_data['stream'],
            location=camera_data.get('location')
        )
        
        print("Creating camera object:", db_camera.__dict__)
        
        db.add(db_camera)
        db.commit()
        db.refresh(db_camera)
        
        result = {
            "source_name": db_camera.source_name,
            "stream_type": db_camera.stream_type,
            "stream": db_camera.stream,
            "location": db_camera.location
        }
        print("Success! Returning:", result)
        return result
        
    except Exception as e:
        db.rollback()
        print("Server error:", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating camera: {str(e)}"
        )
    finally:
        db.close()

@app.delete("/api/cameras/{camera_id}")
async def delete_camera(camera_id: int):
    """Delete a camera from the database"""
    db = SessionLocal()
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

# Add more endpoints as needed for starting/stopping streams, etc.

@app.on_event("startup")
async def startup():
    init_db()  # Initialize database

@app.post("/init-db")
async def initialize_database():
    """Initialize the database tables"""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return {"message": "Database initialized successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initializing database: {str(e)}"
        )

@app.get("/api/detection-stats/summary")
async def get_detection_stats_summary():
    db = SessionLocal()
    try:
        stats = {
            "totalDetections": db.query(func.count(DetectionEvent.id)).scalar(),
            "objectDetections": db.query(func.count(DetectionEvent.id))
                                .filter(DetectionEvent.model_type == "objectDetection").scalar(),
            "segmentations": db.query(func.count(DetectionEvent.id))
                                .filter(DetectionEvent.model_type == "segmentation").scalar(),  
            "poseEstimations": db.query(func.count(DetectionEvent.id))
                                .filter(DetectionEvent.model_type == "pose").scalar()
        }
        return stats
    finally:
        db.close()

@app.get("/api/detection-stats/classes")
async def get_detection_classes(model: str):
    db = SessionLocal()
    try:
        query = db.query(DetectionEvent.class_name.distinct())
        if model != 'all':
            query = query.filter(DetectionEvent.model_type == model)
        
        classes = query.all()
        return [class_name[0] for class_name in classes if class_name[0]]
    finally:
        db.close()

@app.get("/api/detection-stats/daily")
async def get_daily_detection_stats(model: str = 'all', class_name: str = 'all'):
    db = SessionLocal()
    try:
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        
        query = db.query(
            func.date_trunc('hour', DetectionEvent.timestamp).label('hour'),
            func.count(DetectionEvent.id).label('count')
        )
        
        if model != 'all':
            query = query.filter(DetectionEvent.model_type == model)
        if class_name != 'all':
            query = query.filter(DetectionEvent.class_name == class_name)
            
        hourly_stats = (query
            .filter(DetectionEvent.timestamp >= today)
            .filter(DetectionEvent.timestamp < tomorrow)
            .group_by(func.date_trunc('hour', DetectionEvent.timestamp))
            .order_by(func.date_trunc('hour', DetectionEvent.timestamp))
            .all()
        )
        
        return [{"timestamp": stat.hour.isoformat(), "count": stat.count} for stat in hourly_stats]
    finally:
        db.close()

@app.get("/api/detection-stats/weekly")
async def get_weekly_detection_stats(model: str = 'all', class_name: str = 'all'):
    db = SessionLocal()
    try:
        week_ago = datetime.utcnow().date() - timedelta(days=7)
        
        query = db.query(
            func.date_trunc('day', DetectionEvent.timestamp).label('date'),
            func.count(DetectionEvent.id).label('count')
        )
        
        if model != 'all':
            query = query.filter(DetectionEvent.model_type == model)
        if class_name != 'all':
            query = query.filter(DetectionEvent.class_name == class_name)
            
        daily_stats = (query
            .filter(DetectionEvent.timestamp >= week_ago)
            .group_by(func.date_trunc('day', DetectionEvent.timestamp))
            .order_by(func.date_trunc('day', DetectionEvent.timestamp))
            .all()
        )
        
        return [{"date": stat.date.isoformat(), "count": stat.count} for stat in daily_stats]
    finally:
        db.close()

@app.get("/api/camera-threads")
async def get_camera_threads():
    """Get information about currently running camera threads"""
    if not hasattr(app, 'camera_threads_info'):
        return JSONResponse(content={"camera_threads": []})
    
    return JSONResponse(content={
        "camera_threads": list(app.camera_threads_info.values())
    })

# Add these new endpoints for individual camera control

@app.post("/start_camera_stream/{camera_id}")
async def start_camera_stream(camera_id: int, request: ModelRequest):
    """Start stream for a specific camera."""
    global model
    
    try:
        # Set up model based on request
        if request.model_type == 'objectDetection':
            model = YOLO('yolov8s.pt')
        elif request.model_type == 'segmentation':
            model = YOLO('yolov8n-seg.pt')
        elif request.model_type == 'pose':
            model = YOLO('yolov8n-pose.pt')
        else:
            raise HTTPException(status_code=400, detail="Invalid model selected")

        # Get the specific camera
        db = SessionLocal()
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        db.close()

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        if camera_id not in camera_threads or not camera_threads[camera_id].is_alive():
            # Initialize camera resources
            video_captures[camera_id] = cv2.VideoCapture(0)  # or camera.stream for RTSP
            frame_locks[camera_id] = Lock()
            camera_running[camera_id] = True
            detected_objects_this_session[camera_id] = set()
            
            # Create and start thread for this camera
            thread = threading.Thread(
                target=capture_frames_for_camera,
                args=(camera_id,),
                daemon=True
            )
            thread.start()
            camera_threads[camera_id] = thread
            
            app_logger.info(f"► Started Camera {camera_id}")
        
        # Increment active cameras metric
        metrics.active_cameras.inc()
        return {"message": f"Camera {camera_id} stream started", "model_type": request.model_type}
    
    except Exception as e:
        metrics.record_error(
            camera_id=str(camera_id),
            error_type=type(e).__name__,
            component="camera_start"
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop_camera_stream/{camera_id}")
async def stop_camera_stream(camera_id: int):
    """Stop stream for a specific camera."""
    try:
        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            camera_name = camera.source_name if camera else f"Camera {camera_id}"
        finally:
            db.close()

        if camera_id in camera_running:
            app_logger.info(f"Stopping {camera_name} (Thread ID: {camera_threads[camera_id].ident})")
            camera_running[camera_id] = False
            
            if camera_id in camera_threads:
                thread = camera_threads[camera_id]
                thread.join(timeout=2.0)
                
                if not thread.is_alive():
                    app_logger.info("╔════════════════════════════════════")
                    app_logger.info(f"║ {camera_name} Thread Stopped")
                    app_logger.info(f"║ Thread ID {thread.ident} confirmed dead")
                    app_logger.info("╚════════════════════════════════════")
                    
                    # Clean up resources
                    if camera_id in video_captures:
                        video_captures[camera_id].release()
                        del video_captures[camera_id]
                        del frame_locks[camera_id]
                        del latest_frames[camera_id]
                        del camera_threads[camera_id]
                        del camera_running[camera_id]
                else:
                    app_logger.warning(f"Thread for {camera_name} did not stop properly!")

        # Decrement active cameras metric
        metrics.active_cameras.dec()
        return {"message": f"{camera_name} stream stopped"}
    
    except Exception as e:
        metrics.record_error(
            camera_id=str(camera_id),
            error_type=type(e).__name__,
            component="camera_stop"
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start_camera/{camera_id}")
async def start_camera(camera_id: int, camera_name: str = "default"):
    try:
        # Your existing camera start code...
        
        # Update metrics
        metrics.camera_status.labels(
            camera_id=str(camera_id),
            camera_name=camera_name
        ).set(1)
        metrics.active_cameras.inc()
        
        return {"status": "success", "message": f"Camera {camera_id} started"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/stop_camera/{camera_id}")
async def stop_camera(camera_id: int, camera_name: str = "default"):
    try:
        # Your existing camera stop code...
        
        # Update metrics
        metrics.camera_status.labels(
            camera_id=str(camera_id),
            camera_name=camera_name
        ).set(0)
        metrics.active_cameras.dec()
        
        return {"status": "success", "message": f"Camera {camera_id} stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
