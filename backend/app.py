from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
from pathlib import Path

from .schemas import DetectionResult
from .utils import pil_from_upload
from .engines import GeminiEngine
from .core.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Pothole Detector API",
    description="Detect potholes in images using Google Gemini 2.5 Flash",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS.split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini engine
try:
    gemini_engine = GeminiEngine()
    logger.info("Gemini engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini engine: {e}")
    gemini_engine = None

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/api/detect", response_model=DetectionResult)
async def detect_potholes(image: UploadFile = File(...)):
    """Detect potholes in an uploaded image.
    
    Args:
        image: Image file (JPEG/PNG)
        
    Returns:
        DetectionResult with pothole information
        
    Raises:
        HTTPException: If detection fails
    """
    if not gemini_engine:
        raise HTTPException(
            status_code=500,
            detail="Gemini engine not initialized. Check API key configuration."
        )
    
    start_time = time.time()
    
    try:
        # Validate and convert to PIL Image
        pil_image = await pil_from_upload(image)
        logger.info(f"Processing image: {image.filename}, size: {pil_image.size}")
        
        # Detect potholes
        result = await gemini_engine.detect_potholes(pil_image)
        
        elapsed = time.time() - start_time
        logger.info(f"Detection completed in {elapsed:.2f}s")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detection error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}"
        )