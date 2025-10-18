from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class Camera(BaseModel):
    """TII Camera model."""
    cameraId: str
    name: str
    lat: float
    lon: float
    snapshotField: Optional[str] = None
    lastSnapshotUrl: Optional[str] = None
    lastSeenAt: Optional[datetime] = None
    active: bool = True
    raw: Dict[str, Any] = {}

class Box(BaseModel):
    """Bounding box for detected pothole."""
    x: float
    y: float
    w: float
    h: float
    confidence: float

class Observation(BaseModel):
    """Pothole detection observation from camera."""
    cameraId: str
    timestamp: datetime
    snapshotUrl: str
    potholes_present: bool
    count: int
    boxes: List[Box] = []
    engine: str = "gemini"
    notes: Optional[str] = None
    errored: bool = False
    errorMessage: Optional[str] = None