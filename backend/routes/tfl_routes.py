from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
import logging
import json
from pathlib import Path
from datetime import datetime, timezone

from services.tfl_service import TfLService, tfl_status
from services.tfl_scheduler import TfLScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tfl", tags=["TfL JamCams"])

# Global scheduler instance (will be set by server.py)
scheduler: Optional[TfLScheduler] = None
tfl_service: Optional[TfLService] = None

def get_db():
    """Dependency to get database instance."""
    from server import db
    return db

@router.get("/status")
async def get_status(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Get TfL integration status.
    
    Returns:
        Status information including enabled, validated, validation errors, and scheduler state
    """
    cameras_active = 0
    cameras_total = 0
    
    # Only query DB if TfL is validated
    if tfl_status.validated:
        cameras_active = await db.tfl_cameras.count_documents({'active': True})
        cameras_total = await db.tfl_cameras.count_documents({})
    
    status = {
        'enabled': tfl_status.enabled,
        'validated': tfl_status.validated,
        'validationError': tfl_status.validation_error,
        'isSeeded': tfl_status.is_seeded,
        'camerasActive': cameras_active,
        'camerasTotal': cameras_total,
        'lastRunAt': None,
        'nextRunAt': None,
        'lastCycle': {'processed': 0, 'ok': 0, 'errors': 0}
    }
    
    if scheduler:
        scheduler_status = scheduler.get_status()
        status['lastRunAt'] = scheduler_status.get('lastRunAt')
        status['nextRunAt'] = scheduler_status.get('nextRunAt')
        status['lastCycle'] = scheduler_status.get('lastCycle', {'processed': 0, 'ok': 0, 'errors': 0})
    
    return status

@router.post("/sync")
async def sync_cameras(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Sync JamCams from TfL Unified API or load from seed file.
    
    Returns:
        Statistics about synced cameras
        
    Raises:
        409: If TfL not enabled
    """
    if not tfl_status.enabled:
        raise HTTPException(
            status_code=409,
            detail="TfL disabled by config. Set TFL_ENABLE=true in .env"
        )
    
    if not tfl_service:
        raise HTTPException(status_code=500, detail="TfL service not initialized")
    
    try:
        # Try fetching from API first
        try:
            places = tfl_service.fetch_jamcams()
        except Exception as api_error:
            logger.warning(f"TfL API fetch failed: {api_error}. Trying seed file...")
            places = []
        
        # If API failed, try seed file
        if not places:
            seed_path = Path(tfl_service.seed_file)
            if seed_path.exists():
                with open(seed_path, 'r') as f:
                    seed_data = json.load(f)
                
                if seed_data and isinstance(seed_data, list):
                    logger.info(f"Loading {len(seed_data)} cameras from seed file")
                    inserted = 0
                    updated = 0
                    
                    for cam in seed_data:
                        result = await db.tfl_cameras.update_one(
                            {'cameraId': cam['cameraId']},
                            {
                                '$set': {
                                    'name': cam['name'],
                                    'lat': float(cam['lat']),
                                    'lon': float(cam['lon']),
                                    'imageUrl': cam.get('imageUrl'),
                                    'active': bool(cam.get('imageUrl')),
                                    'seed': True,
                                    'raw': cam
                                },
                                '$setOnInsert': {
                                    'cameraId': cam['cameraId'],
                                    'lastSeenAt': None
                                }
                            },
                            upsert=True
                        )
                        
                        if result.upserted_id:
                            inserted += 1
                        else:
                            updated += 1
                    
                    cameras_active = await db.tfl_cameras.count_documents({'active': True})
                    tfl_status.set_validated(True, None, seeded=True)
                    
                    return {
                        'inserted': inserted,
                        'updated': updated,
                        'inactive': 0,
                        'camerasActive': cameras_active,
                        'source': 'seed'
                    }
            
            # Neither API nor seed worked
            raise HTTPException(
                status_code=503,
                detail="TfL API unavailable and no seed file found. Check TFL_BASE or provide TFL_SEED_FILE"
            )
        
        # Process API results
        inserted = 0
        updated = 0
        inactive = 0
        
        for place in places:
            camera_doc = tfl_service.parse_camera(place)
            if not camera_doc:
                inactive += 1
                continue
            
            camera_id = camera_doc['cameraId']
            
            # Upsert camera
            result = await db.tfl_cameras.update_one(
                {'cameraId': camera_id},
                {
                    '$set': camera_doc,
                    '$setOnInsert': {
                        'cameraId': camera_id,
                        'lastSeenAt': None
                    }
                },
                upsert=True
            )
            
            if result.upserted_id:
                inserted += 1
            else:
                updated += 1
        
        logger.info(f"TfL camera sync complete: {inserted} inserted, {updated} updated, {inactive} inactive")
        
        # Get total active cameras
        cameras_active = await db.tfl_cameras.count_documents({'active': True})
        
        # Update validation status
        if cameras_active > 0:
            tfl_status.set_validated(True, None, seeded=False)
        
        return {
            'inserted': inserted,
            'updated': updated,
            'inactive': inactive,
            'camerasActive': cameras_active,
            'source': 'api'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync TfL cameras: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync cameras: {str(e)}")

@router.post("/run-once")
async def run_once(
    limit: int = Query(default=50, ge=1, le=150),
    cameraId: Optional[str] = Query(default=None, alias="cameraId")
):
    """Manually trigger one polling cycle.
    
    Args:
        limit: Maximum number of cameras to process
        cameraId: Optional camera ID to process only one camera
    
    Returns:
        Cycle statistics
        
    Raises:
        409: If TfL not validated and no seed
    """
    if not tfl_status.validated:
        # Check if we have any cameras (seeded)
        from server import db
        camera_count = await db.tfl_cameras.count_documents({'active': True})
        
        if camera_count == 0:
            raise HTTPException(
                status_code=409,
                detail="TfL not validated and no cameras available. Run POST /api/tfl/sync first."
            )
    
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    
    try:
        stats = await scheduler.run_cycle(limit=limit, camera_id=cameraId)
        return {
            'success': True,
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Manual TfL run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Run failed: {str(e)}")

@router.get("/cameras")
async def list_cameras(db: AsyncIOMotorDatabase = Depends(get_db)):
    """List all TfL cameras.
    
    Returns:
        List of camera objects
    """
    cameras = await db.tfl_cameras.find(
        {},
        {
            '_id': 0,
            'cameraId': 1,
            'name': 1,
            'lat': 1,
            'lon': 1,
            'lastSeenAt': 1,
            'imageUrl': 1,
            'active': 1,
            'seed': 1
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
    observation = await db.tfl_observations.find_one(
        {'cameraId': camera_id},
        {'_id': 0},
        sort=[('timestamp', -1)]
    )
    
    if not observation:
        raise HTTPException(status_code=404, detail="No observations found")
    
    return observation

@router.get("/observations")
async def list_observations(
    cameraId: Optional[str] = Query(default=None, alias="cameraId"),
    limit: int = 10,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """List observations with optional camera filter.
    
    Args:
        cameraId: Optional camera ID filter
        limit: Maximum number of results
        
    Returns:
        List of observations
    """
    query = {}
    if cameraId:
        query['cameraId'] = cameraId
    
    observations = await db.tfl_observations.find(
        query,
        {'_id': 0}
    ).sort('timestamp', -1).limit(limit).to_list(limit)
    
    return observations
