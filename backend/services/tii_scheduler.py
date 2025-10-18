import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image
import io

from core.config import config
from services.arcgis_service import ArcGISService
from engines import GeminiEngine

logger = logging.getLogger(__name__)

class TIIScheduler:
    """Background scheduler for TII camera polling and pothole detection."""
    
    def __init__(self, db: AsyncIOMotorDatabase, gemini_engine: GeminiEngine):
        self.db = db
        self.gemini_engine = gemini_engine
        self.arcgis_service = ArcGISService()
        
        self.running = False
        self.last_run_at = None
        self.next_run_at = None
        self.last_cycle_stats = {
            'processed': 0,
            'ok': 0,
            'errors': 0
        }
        self.camera_offset = 0
        
    async def start(self):
        """Start the background polling loop."""
        if self.running:
            logger.warning("Scheduler already running")
            return
            
        self.running = True
        logger.info(f"Starting TII scheduler with {config.TII_POLL_INTERVAL_MIN} minute interval")
        
        # Run in background
        asyncio.create_task(self._polling_loop())
    
    async def stop(self):
        """Stop the background polling loop."""
        self.running = False
        logger.info("Stopping TII scheduler")
    
    async def _polling_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                await self.run_cycle()
                
                # Wait for next interval
                interval_seconds = config.TII_POLL_INTERVAL_MIN * 60
                self.next_run_at = datetime.now(timezone.utc)
                self.next_run_at = self.next_run_at.replace(second=0, microsecond=0)
                
                # Add interval
                import datetime as dt
                self.next_run_at = self.next_run_at + dt.timedelta(seconds=interval_seconds)
                
                logger.info(f"Next run scheduled at {self.next_run_at}")
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def run_cycle(self) -> Dict[str, Any]:
        """Run one polling cycle.
        
        Returns:
            Stats dictionary with processed, ok, errors counts
        """
        self.last_run_at = datetime.now(timezone.utc)
        stats = {'processed': 0, 'ok': 0, 'errors': 0}
        
        try:
            # Get active cameras
            cameras_cursor = self.db.cameras.find({'active': True}).skip(self.camera_offset)
            cameras = await cameras_cursor.to_list(length=config.MAX_CAMERAS_PER_CYCLE)
            
            if not cameras:
                # Reset offset if we've processed all cameras
                self.camera_offset = 0
                logger.info("No more cameras to process, resetting offset")
                self.last_cycle_stats = stats
                return stats
            
            logger.info(f"Processing {len(cameras)} cameras starting at offset {self.camera_offset}")
            
            for camera in cameras:
                stats['processed'] += 1
                
                try:
                    await self._process_camera(camera)
                    stats['ok'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing camera {camera.get('cameraId')}: {e}")
                    stats['errors'] += 1
                    
                    # Store error observation
                    await self.db.observations.insert_one({
                        'cameraId': camera.get('cameraId'),
                        'timestamp': datetime.now(timezone.utc),
                        'snapshotUrl': camera.get('lastSnapshotUrl', ''),
                        'potholes_present': False,
                        'count': 0,
                        'boxes': [],
                        'engine': 'gemini',
                        'notes': None,
                        'errored': True,
                        'errorMessage': str(e)
                    })
            
            # Update offset for next cycle
            self.camera_offset += len(cameras)
            
        except Exception as e:
            logger.error(f"Error in run cycle: {e}", exc_info=True)
            stats['errors'] += 1
        
        self.last_cycle_stats = stats
        logger.info(f"Cycle complete: {stats}")
        return stats
    
    async def _process_camera(self, camera: Dict[str, Any]):
        """Process a single camera: fetch snapshot, detect potholes, store result.
        
        Args:
            camera: Camera document from database
        """
        camera_id = camera.get('cameraId')
        snapshot_field = camera.get('snapshotField')
        
        if not snapshot_field:
            raise ValueError(f"No snapshot field configured for camera {camera_id}")
        
        # Get snapshot URL from raw attributes
        raw_attrs = camera.get('raw', {})
        snapshot_url = raw_attrs.get(snapshot_field)
        
        if not snapshot_url:
            raise ValueError(f"No snapshot URL found in field {snapshot_field}")
        
        # Download snapshot
        logger.info(f"Downloading snapshot for camera {camera_id} from {snapshot_url}")
        image_bytes = self.arcgis_service.download_snapshot(snapshot_url)
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Run pothole detection
        logger.info(f"Running pothole detection for camera {camera_id}")
        detection_result = await self.gemini_engine.detect_potholes(image)
        
        # Store observation
        observation = {
            'cameraId': camera_id,
            'timestamp': datetime.now(timezone.utc),
            'snapshotUrl': snapshot_url,
            'potholes_present': detection_result.potholes_present,
            'count': detection_result.count,
            'boxes': [box.model_dump() for box in detection_result.boxes],
            'engine': detection_result.engine,
            'notes': detection_result.notes,
            'errored': False,
            'errorMessage': None
        }
        
        await self.db.observations.insert_one(observation)
        
        # Update camera last seen
        await self.db.cameras.update_one(
            {'cameraId': camera_id},
            {
                '$set': {
                    'lastSnapshotUrl': snapshot_url,
                    'lastSeenAt': datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"Camera {camera_id}: {detection_result.count} potholes detected")
    
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