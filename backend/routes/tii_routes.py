from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
import logging
from datetime import datetime, timezone

from services.arcgis_service import ArcGISService
from services.tii_scheduler import TIIScheduler
from models import Camera, Observation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tii", tags=["TII Cameras"])

# Global scheduler instance (will be set by server.py)
scheduler: Optional[TIIScheduler] = None

def get_db():
    """Dependency to get database instance."""
    from server import db
    return db

@router.post("/sync-cameras")
async def sync_cameras(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Sync cameras from TII ArcGIS FeatureServer.
    
    Fetches all camera features and upserts into the database.
    
    Returns:
        Statistics about synced cameras
    """
    try:
        arcgis_service = ArcGISService()
        features = arcgis_service.fetch_tii_features()
        
        inserted = 0
        updated = 0
        inactive = 0
        
        for feature in features:
            attributes = feature.get('attributes', {})
            geometry = feature.get('geometry', {})
            
            # Extract camera ID (try multiple common fields)
            camera_id = (
                attributes.get('OBJECTID') or 
                attributes.get('ID') or 
                attributes.get('CameraID') or 
                str(attributes.get('FID', f"cam_{inserted + updated}"))
            )
            camera_id = str(camera_id)
            
            # Extract name
            name = (
                attributes.get('Name') or
                attributes.get('Title') or
                attributes.get('Location') or
                attributes.get('Description') or
                f"Camera {camera_id}"
            )
            
            # Get coordinates
            lon = geometry.get('x')
            lat = geometry.get('y')
            
            if not (lon and lat):
                logger.warning(f"Skipping camera {camera_id}: missing coordinates")
                inactive += 1
                continue
            
            # Detect snapshot field
            snapshot_field = arcgis_service.detect_snapshot_field(attributes)
            active = snapshot_field is not None
            
            if not active:
                inactive += 1
            
            # Upsert camera
            result = await db.cameras.update_one(
                {'cameraId': camera_id},
                {
                    '$set': {
                        'name': name,
                        'lat': lat,
                        'lon': lon,
                        'snapshotField': snapshot_field,
                        'active': active,
                        'raw': attributes
                    },
                    '$setOnInsert': {
                        'lastSnapshotUrl': None,
                        'lastSeenAt': None
                    }
                },
                upsert=True
            )
            
            if result.upserted_id:
                inserted += 1
            else:
                updated += 1
        
        logger.info(f"Camera sync complete: {inserted} inserted, {updated} updated, {inactive} inactive")
        
        # Get total active cameras
        cameras_active = await db.cameras.count_documents({'active': True})
        
        return {
            'inserted': inserted,
            'updated': updated,
            'inactive': inactive,
            'camerasActive': cameras_active
        }
        
    except Exception as e:
        logger.error(f"Failed to sync cameras: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync cameras: {str(e)}")

@router.post("/run-once")
async def run_once():
    """Manually trigger one polling cycle.
    
    Returns:
        Cycle statistics
    """
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    
    try:
        stats = await scheduler.run_cycle()
        return {
            'success': True,
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Manual run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Run failed: {str(e)}")

@router.get("/status")
async def get_status(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get scheduler and camera status.
    
    Returns:
        Status information
    """
    cameras_active = await db.cameras.count_documents({'active': True})
    
    status = {
        'camerasActive': cameras_active,
        'lastRunAt': None,
        'nextRunAt': None,
        'lastCycle': {'processed': 0, 'ok': 0, 'errors': 0}
    }
    
    if scheduler:
        scheduler_status = scheduler.get_status()
        status.update(scheduler_status)
    
    return status

@router.get("/cameras")
async def list_cameras(db: AsyncIOMotorDatabase = Depends(get_db)):
    """List all cameras.
    
    Returns:
        List of camera objects
    """
    cameras = await db.cameras.find(
        {},
        {
            '_id': 0,
            'cameraId': 1,
            'name': 1,
            'lat': 1,
            'lon': 1,
            'lastSeenAt': 1,
            'lastSnapshotUrl': 1,
            'active': 1
        }
    ).to_list(1000)
    
    return cameras

@router.get("/cameras/{camera_id}/latest")
async def get_camera_latest(camera_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get latest observation for a camera.
    
    Args:
        camera_id: Camera ID
        
    Returns:
        Latest observation or 404
    """
    observation = await db.observations.find_one(
        {'cameraId': camera_id},
        {'_id': 0},
        sort=[('timestamp', -1)]
    )
    
    if not observation:
        raise HTTPException(status_code=404, detail="No observations found")
    
    return observation

@router.get("/observations")
async def list_observations(
    camera_id: Optional[str] = None,
    limit: int = 10,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """List observations with optional camera filter.
    
    Args:
        camera_id: Optional camera ID filter
        limit: Maximum number of results
        
    Returns:
        List of observations
    """
    query = {}
    if camera_id:
        query['cameraId'] = camera_id
    
    observations = await db.observations.find(
        query,
        {'_id': 0}
    ).sort('timestamp', -1).limit(limit).to_list(limit)
    
    return observations