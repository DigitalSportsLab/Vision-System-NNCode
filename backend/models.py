from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class DetectionEvent(Base):
    __tablename__ = 'detection_events'
    
    id = Column(Integer, primary_key=True, index=True)
    model_type = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    class_name = Column(String)
    camera_id = Column(Integer, index=True)
    camera_name = Column(String)

class Camera(Base):
    __tablename__ = 'cameras'
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, nullable=False, unique=True)
    stream_type = Column(String)
    stream = Column(String)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, source_name, stream_type, stream, location=None):
        self.source_name = source_name
        self.stream_type = stream_type
        self.stream = stream
        self.location = location
        self.created_at = datetime.utcnow()