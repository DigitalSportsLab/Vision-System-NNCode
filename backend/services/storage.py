# backend/services/storage.py
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session as OrmSession
from backend.db_settings import SessionLocal
from backend.models import PoseFrame
import time

class DbSink:
    """Schreibt Tracks/Keypoints in pose_frames (schlank)."""
    def __init__(self, batch_size: int = 64):
        self.batch_size = batch_size
        self._buffer: List[PoseFrame] = []

    def write(self, session_id: int, payload: Dict[str, Any]) -> None:
        tracks = payload.get("tracks", [])
        for t in tracks:
            kp = t.get("keypoints")
            bbox = t.get("bbox") or [None, None, None, None]
            pf = PoseFrame(
                session_id=session_id,
                ts_ms=int(t.get("ts_ms")),
                track_id=t.get("track_id"),
                x=bbox[0], y=bbox[1], w=bbox[2], h=bbox[3],
                keypoints=kp
            )
            self._buffer.append(pf)
        if len(self._buffer) >= self.batch_size:
            self._flush_once()

    def _flush_once(self):
        if not self._buffer:
            return
        db: OrmSession = SessionLocal()
        try:
            db.add_all(self._buffer)
            db.commit()
            self._buffer.clear()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def flush(self) -> None:
        self._flush_once()

    def close(self) -> None:
        self._flush_once()
