from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.db_settings import SessionLocal
from backend.models import DetectionEvent, Camera

router = APIRouter()

@router.get("")
async def get_detection_stats_summary():
    db: Session = SessionLocal()
    try:
        stats = {
            "totalDetections": db.query(func.count(DetectionEvent.id)).scalar(),
            "objectDetections": db.query(func.count(DetectionEvent.id))
                                  .filter(DetectionEvent.model_type == "objectDetection").scalar(),
            "segmentations": db.query(func.count(DetectionEvent.id))
                                  .filter(DetectionEvent.model_type == "segmentation").scalar(),
            "poseEstimations": db.query(func.count(DetectionEvent.id))
                                  .filter(DetectionEvent.model_type == "pose").scalar(),
        }
        return stats
    finally:
        db.close()


@router.get("/classes")
async def get_detection_classes(model: str):
    db: Session = SessionLocal()
    try:
        query = db.query(DetectionEvent.class_name.distinct())
        if model != 'all':
            query = query.filter(DetectionEvent.model_type == model)
        classes = query.all()
        return [c[0] for c in classes if c[0]]
    finally:
        db.close()


@router.get("/daily")
async def get_daily_detection_stats(model: str = 'all', class_name: str = 'all'):
    db: Session = SessionLocal()
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


@router.get("/weekly")
async def get_weekly_detection_stats(model: str = 'all', class_name: str = 'all'):
    db: Session = SessionLocal()
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


@router.get("/real-time")
async def get_real_time_stats(request: Request):
    """Get real-time detection statistics for the last hour"""
    db: Session = SessionLocal()
    try:
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        minute_stats = db.query(
            func.date_trunc('minute', DetectionEvent.timestamp).label('minute'),
            func.count(DetectionEvent.id).label('count')
        ).filter(
            DetectionEvent.timestamp >= one_hour_ago
        ).group_by(
            func.date_trunc('minute', DetectionEvent.timestamp)
        ).order_by(
            func.date_trunc('minute', DetectionEvent.timestamp).desc()
        ).limit(60).all()

        # Aktive Kameras aus App-Context (wie im Original)
        active_threads = getattr(request.app, 'camera_threads_info', {})
        active_cameras = len(active_threads)

        latest_detections = db.query(DetectionEvent).order_by(
            DetectionEvent.timestamp.desc()
        ).limit(10).all()

        return {
            "detectionRate": [{"time": stat.minute.isoformat(), "count": stat.count} for stat in minute_stats],
            "activeCameras": active_cameras,
            "latestDetections": [{
                "id": d.id,
                "model_type": d.model_type,
                "class_name": d.class_name,
                "camera_name": d.camera_name,
                "timestamp": d.timestamp.isoformat()
            } for d in latest_detections]
        }
    finally:
        db.close()


@router.get("/top-classes")
async def get_top_classes(limit: int = 10, days: int = 7):
    """Get top detected classes over a specified period"""
    db: Session = SessionLocal()
    try:
        since_date = datetime.utcnow() - timedelta(days=days)

        top_classes = db.query(
            DetectionEvent.class_name,
            func.count(DetectionEvent.id).label('count')
        ).filter(
            DetectionEvent.timestamp >= since_date,
            DetectionEvent.class_name.isnot(None)
        ).group_by(
            DetectionEvent.class_name
        ).order_by(
            func.count(DetectionEvent.id).desc()
        ).limit(limit).all()

        return [{
            "class_name": class_name,
            "count": count,
            "percentage": 0  # Frontend berechnet Prozent
        } for class_name, count in top_classes]
    finally:
        db.close()


@router.get("/camera-performance")
async def get_camera_performance(request: Request):
    """Get detection statistics per camera"""
    db: Session = SessionLocal()
    try:
        cameras = db.query(Camera).all()
        threads_info = getattr(request.app, 'camera_threads_info', {})

        camera_stats = []
        for camera in cameras:
            detection_count = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.camera_id == camera.id
            ).scalar()

            last_detection = db.query(DetectionEvent.timestamp).filter(
                DetectionEvent.camera_id == camera.id
            ).order_by(DetectionEvent.timestamp.desc()).first()

            is_active = camera.id in threads_info

            camera_stats.append({
                "id": camera.id,
                "name": camera.source_name,
                "location": camera.location,
                "detectionCount": detection_count,
                "lastDetection": last_detection[0].isoformat() if last_detection else None,
                "isActive": is_active,
                "uptime": "N/A"
            })

        return camera_stats
    finally:
        db.close()


@router.get("/hourly-pattern")
async def get_hourly_pattern(days: int = 30):
    """Get average detection patterns by hour of day"""
    db: Session = SessionLocal()
    try:
        since_date = datetime.utcnow() - timedelta(days=days)

        hourly_avg = db.query(
            func.extract('hour', DetectionEvent.timestamp).label('hour'),
            func.count(DetectionEvent.id).label('total_count')
        ).filter(
            DetectionEvent.timestamp >= since_date
        ).group_by(
            func.extract('hour', DetectionEvent.timestamp)
        ).order_by(
            func.extract('hour', DetectionEvent.timestamp)
        ).all()

        hourly_pattern = []
        for hour, total_count in hourly_avg:
            avg_count = total_count / days
            hourly_pattern.append({"hour": int(hour), "avgCount": round(avg_count, 2)})

        return hourly_pattern
    finally:
        db.close()
