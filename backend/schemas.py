from pydantic import BaseModel
from typing import Literal, List

class Box(BaseModel):
    """Bounding box for a detected pothole."""
    x: float
    y: float
    w: float
    h: float
    confidence: float

class DetectionResult(BaseModel):
    """Result of pothole detection."""
    engine: Literal["gemini"] = "gemini"
    potholes_present: bool
    count: int
    boxes: List[Box] = []
    notes: str | None = None