from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path

# Import the pothole detector app
from app import app as pothole_app, gemini_engine

# Import TII routes and scheduler
from routes import tii_routes
from services.tii_scheduler import TIIScheduler
from services.arcgis_service import ArcGISService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Use the pothole detector app as the main app
app = pothole_app

# Include TII routes
app.include_router(tii_routes.router)

# Initialize ArcGIS service and TII scheduler
arcgis_service = ArcGISService()
scheduler = TIIScheduler(db, gemini_engine)
tii_routes.scheduler = scheduler  # Set global scheduler for routes
tii_routes.arcgis_service = arcgis_service  # Set global ArcGIS service for routes

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Start TII scheduler on application startup."""
    logger.info("Starting TII camera integration...")
    
    # Validate ArcGIS layer URL
    is_valid = arcgis_service.validate_layer_url()
    
    if is_valid:
        logger.info("TII validation successful. Starting scheduler...")
        await scheduler.start()
    else:
        if not config.TII_ENABLE:
            logger.info("TII integration disabled by configuration (TII_ENABLE=false)")
        else:
            logger.warning(f"TII integration degraded: {arcgis_service.validation_error or 'Validation failed'}. Scheduler will not start.")

@app.on_event("shutdown")
async def shutdown_db_client():
    """Stop scheduler and close database connection."""
    logger.info("Shutting down...")
    await scheduler.stop()
    client.close()