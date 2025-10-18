import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image
import io

from core.config import config
from services.tfl_service import TfLService
from engines import GeminiEngine

logger = logging.getLogger(__name__)

class TfLScheduler:
    """Background scheduler for TfL JamCams polling and pothole detection."""
    
    def __init__(self, db: AsyncIOMotorDatabase, gemini_engine: GeminiEngine):
        self.db = db
        self.gemini_engine = gemini_engine
        self.tfl_service = TfLService()
        
        self.running = False
        self.last_run_at = None
        self.next_run_at = None
        self.last_cycle_stats = {
            'processed': 0,
            'ok': 0,
            'errors': 0,
            'notFound404': 0
        }
        self.camera_offset = 0
        
    async def start(self):
        """Start the background polling loop."""
        if self.running:
            logger.warning("TfL scheduler already running")
            return
            
        self.running = True
        logger.info(f"Starting TfL scheduler with {config.TFL_POLL_INTERVAL_MIN} minute interval")
        
        # Run in background
        asyncio.create_task(self._polling_loop())
    
    async def stop(self):
        """Stop the background polling loop."""
        self.running = False
        logger.info("Stopping TfL scheduler")
    
    async def _polling_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                await self.run_cycle()
                
                # Wait for next interval
                interval_seconds = config.TFL_POLL_INTERVAL_MIN * 60
                self.next_run_at = datetime.now(timezone.utc)
                self.next_run_at = self.next_run_at.replace(second=0, microsecond=0)
                
                # Add interval
                import datetime as dt
                self.next_run_at = self.next_run_at + dt.timedelta(seconds=interval_seconds)
                
                logger.info(f"Next TfL run scheduled at {self.next_run_at}")
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in TfL polling loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def run_cycle(self, limit: int = None, camera_id: str = None) -> Dict[str, Any]:
        """Run one polling cycle.
        
        Args:
            limit: Maximum number of cameras to process (overrides config)
            camera_id: Optional camera ID to process only one camera
        
        Returns:
            Stats dictionary with processed, ok, errors, notFound404 counts
        """
        self.last_run_at = datetime.now(timezone.utc)
        stats = {'processed': 0, 'ok': 0, 'errors': 0, 'notFound404': 0}
        
        try:
            # If camera_id provided, process only that camera
            if camera_id:
                camera = await self.db.tfl_cameras.find_one({'cameraId': camera_id, 'active': True})
                cameras = [camera] if camera else []
            else:
                # Get active cameras
                max_limit = limit or config.TFL_MAX_CAMERAS_PER_CYCLE
                cameras_cursor = self.db.tfl_cameras.find({'active': True}).skip(self.camera_offset)
                cameras = await cameras_cursor.to_list(length=max_limit)
            
            if not cameras:
                # Reset offset if we've processed all cameras
                self.camera_offset = 0
                logger.info("No more TfL cameras to process, resetting offset")
                self.last_cycle_stats = stats
                return stats
            
            logger.info(f"Processing {len(cameras)} TfL cameras starting at offset {self.camera_offset}")
            
            for camera in cameras:
                stats['processed'] += 1
                
                try:
                    await self._process_camera(camera)
                    stats['ok'] += 1
                    
                except Exception as e:
                    # Check if it's a 404 error
                    if str(e) == "NOT_FOUND_404":
                        logger.warning(f"TfL camera {camera.get('cameraId')}: 404 not found")
                        stats['notFound404'] += 1
                    else:
                        logger.error(f"Error processing TfL camera {camera.get('cameraId')}: {e}")
                        stats['errors'] += 1
                        
                        # Store error observation (only for non-404 errors, 404s are already stored in _process_camera)
                        await self.db.tfl_observations.insert_one({
                            'cameraId': camera.get('cameraId'),
                            'timestamp': datetime.now(timezone.utc),
                            'snapshotUrl': camera.get('imageUrl', ''),
                            'potholes_present': False,
                            'count': 0,
                            'boxes': [],
                            'engine': 'gemini',
                            'errored': True,
                            'errorMessage': str(e)[:500]
                        })
            
            # Update offset for next cycle
            if not camera_id:
                self.camera_offset += len(cameras)
            
        except Exception as e:
            logger.error(f"Error in TfL run cycle: {e}", exc_info=True)
            stats['errors'] += 1
        
        self.last_cycle_stats = stats
        logger.info(f"TfL cycle complete: {stats}")
        return stats
    
    async def _process_camera(self, camera: Dict[str, Any]):
        """Process a single camera: fetch snapshot, detect potholes, store result.
        
        Args:
            camera: Camera document from database
            
        Raises:
            Special exception for 404s to track separately
        """
        camera_id = camera.get('cameraId')
        image_url = camera.get('imageUrl')
        
        if not image_url:
            raise ValueError(f"No imageUrl for camera {camera_id}")
        
        # HEAD check first to avoid downloading 404s
        logger.info(f"HEAD check for TfL camera {camera_id}: {image_url}")
        is_ok, status_code = self.tfl_service.head_ok(image_url)
        
        if not is_ok:
            error_msg = f"HEAD {status_code or 'failed'} for {image_url}"
            logger.warning(f"TfL camera {camera_id}: {error_msg}")
            
            # Store error observation
            await self.db.tfl_observations.insert_one({
                'cameraId': camera_id,
                'timestamp': datetime.now(timezone.utc),
                'snapshotUrl': image_url,
                'potholes_present': False,
                'count': 0,
                'boxes': [],
                'engine': 'gemini',
                'notes': None,
                'errored': True,
                'errorMessage': error_msg
            })
            
            # Raise special exception to indicate 404
            if status_code == 404:
                raise Exception("NOT_FOUND_404")
            else:
                raise Exception(error_msg)
        
        # Download image
        logger.info(f"Downloading image for TfL camera {camera_id} from {image_url}")
        image_bytes = self.tfl_service.download_image(image_url)
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Run pothole detection
        logger.info(f"Running pothole detection for TfL camera {camera_id}")
        detection_result = await self.gemini_engine.detect_potholes(image)
        
        # Store observation
        observation = {
            'cameraId': camera_id,
            'timestamp': datetime.now(timezone.utc),
            'snapshotUrl': image_url,
            'potholes_present': detection_result.potholes_present,
            'count': detection_result.count,
            'boxes': [box.model_dump() for box in detection_result.boxes],
            'engine': detection_result.engine,
            'notes': detection_result.notes,
            'errored': False,
            'errorMessage': None
        }
        
        await self.db.tfl_observations.insert_one(observation)
        
        # Update camera last seen
        await self.db.tfl_cameras.update_one(
            {'cameraId': camera_id},
            {
                '$set': {
                    'lastSeenAt': datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"TfL camera {camera_id}: {detection_result.count} potholes detected")
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status.
        
        Returns:
            Status dictionary
        """
        return {
            'running': self.running,
            'lastRunAt': self.last_run_at.isoformat() if self.last_run_at else None,
            'nextRunAt': self.next_run_at.isoformat() if self.next_run_at else None,
            'lastCycle': self.last_cycle_stats
        }