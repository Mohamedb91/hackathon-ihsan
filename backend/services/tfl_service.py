import requests
import logging
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from core.config import config

logger = logging.getLogger(__name__)

class TfLValidationStatus:
    """Singleton to hold TfL validation state."""
    def __init__(self):
        self.enabled = config.TFL_ENABLE
        self.validated = False
        self.validation_error: Optional[str] = None
        self.is_seeded = False
    
    def set_validated(self, success: bool, error: Optional[str] = None, seeded: bool = False):
        self.validated = success
        self.validation_error = error
        self.is_seeded = seeded

# Global singleton instance
tfl_status = TfLValidationStatus()

class TfLService:
    """Service for fetching TfL JamCams data from TfL Unified API."""
    
    def __init__(self):
        self.base_url = config.TFL_BASE
        self.app_id = config.TFL_APP_ID
        self.app_key = config.TFL_APP_KEY
        self.seed_file = config.TFL_SEED_FILE
        
    def validate_api(self) -> bool:
        """Validate the TfL API by fetching JamCams.
        
        Returns:
            True if valid, False otherwise. Updates global tfl_status.
        """
        if not config.TFL_ENABLE:
            tfl_status.set_validated(False, "TfL disabled by configuration (TFL_ENABLE=false)")
            logger.info("TfL integration disabled by config")
            return False
            
        try:
            places = self.fetch_jamcams()
            
            if not places:
                # Try loading seed file
                if self._load_seed_file():
                    return True
                
                error_msg = "No JamCams returned from TfL API. Check TFL_BASE or load a seed file."
                tfl_status.set_validated(False, error_msg)
                logger.error(f"ERROR: TfL validation failed: {error_msg}")
                return False
            
            # Count how many have imageUrl
            active_count = sum(1 for p in places if self._get_image_url(p))
            
            if active_count == 0:
                error_msg = f"Fetched {len(places)} JamCams but none have imageUrl"
                tfl_status.set_validated(False, error_msg)
                logger.error(f"ERROR: TfL validation failed: {error_msg}")
                return False
            
            logger.info(f"✓ TfL API validated successfully ({active_count} cameras with images)")
            tfl_status.set_validated(True, None, False)
            return True
            
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout connecting to TfL API (5s connect, 10s read): {self.base_url}"
            tfl_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TfL validation failed: {error_msg}")
            return False
        except requests.exceptions.ConnectionError as e:
            error_msg = f"DNS resolution or network error connecting to TfL API: {str(e)[:200]}"
            tfl_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TfL validation failed: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Unexpected error validating TfL API: {str(e)[:200]}"
            tfl_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TfL validation failed: {error_msg}", exc_info=True)
            return False
    
    def _load_seed_file(self) -> bool:
        """Load seed file if API is unavailable.
        
        Returns:
            True if seed loaded successfully
        """
        seed_path = Path(self.seed_file)
        if not seed_path.exists():
            logger.warning(f"Seed file not found: {self.seed_file}")
            return False
        
        try:
            with open(seed_path, 'r') as f:
                seed_data = json.load(f)
            
            if not seed_data or not isinstance(seed_data, list):
                logger.warning(f"Invalid seed file format: {self.seed_file}")
                return False
            
            logger.info(f"Loaded {len(seed_data)} cameras from seed file")
            tfl_status.set_validated(True, None, seeded=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to load seed file: {e}")
            return False
        
    def fetch_jamcams(self) -> List[Dict[str, Any]]:
        """Fetch all JamCam places from TfL Unified API.
        
        Returns:
            List of Place objects
            
        Raises:
            Exception: If fetch fails
        """
        try:
            url = f"{self.base_url}/Place/Type/JamCam"
            params = {}
            
            if self.app_id:
                params['app_id'] = self.app_id
            if self.app_key:
                params['app_key'] = self.app_key
            
            logger.info(f"Fetching JamCams from {url}")
            response = requests.get(url, params=params, timeout=(5, 10))
            response.raise_for_status()
            
            places = response.json()
            
            if not isinstance(places, list):
                raise Exception(f"Unexpected response format: {type(places)}")
            
            logger.info(f"Fetched {len(places)} JamCam places from TfL")
            return places
            
        except Exception as e:
            logger.error(f"Failed to fetch JamCams: {e}")
            raise
    
    def _get_image_url(self, place: Dict[str, Any]) -> Optional[str]:
        """Extract imageUrl from Place additionalProperties.
        
        Args:
            place: Place object from TfL API
            
        Returns:
            Image URL or None
        """
        additional_props = place.get('additionalProperties', [])
        if not isinstance(additional_props, list):
            return None
        
        for prop in additional_props:
            if prop.get('key') == 'imageUrl':
                return prop.get('value')
        
        return None
    
    def parse_camera(self, place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a Place object into camera document.
        
        Args:
            place: Place object from TfL API
            
        Returns:
            Camera document dict or None if invalid
        """
        try:
            camera_id = place.get('id')
            if not camera_id:
                return None
            
            name = place.get('commonName', f"Camera {camera_id}")
            lat = place.get('lat')
            lon = place.get('lon')
            
            if lat is None or lon is None:
                logger.warning(f"Skipping camera {camera_id}: missing coordinates")
                return None
            
            image_url = self._get_image_url(place)
            active = bool(image_url)
            
            return {
                'cameraId': camera_id,
                'name': name,
                'lat': float(lat),
                'lon': float(lon),
                'imageUrl': image_url,
                'active': active,
                'seed': False,
                'raw': place
            }
            
        except Exception as e:
            logger.error(f"Failed to parse camera: {e}")
            return None
    
    def download_image(self, url: str) -> bytes:
        """Download camera image.
        
        Args:
            url: Image URL
            
        Returns:
            Image bytes
            
        Raises:
            Exception: If download fails
        """
        try:
            response = requests.get(url, timeout=(5, 10), stream=True)
            response.raise_for_status()
            
            # Read with size limit (2MB)
            content = response.content
            if len(content) > 2 * 1024 * 1024:
                raise ValueError(f"Image too large: {len(content)} bytes")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise