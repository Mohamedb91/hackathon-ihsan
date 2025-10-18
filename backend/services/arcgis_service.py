import requests
import logging
from typing import List, Dict, Any, Optional
from core.config import config

logger = logging.getLogger(__name__)

class ArcGISService:
    """Service for fetching TII camera data from ArcGIS REST API."""
    
    def __init__(self):
        self.layer_url = config.TII_ARCGIS_LAYER_URL
        
    def fetch_tii_features(self) -> List[Dict[str, Any]]:
        """Fetch all camera features from TII ArcGIS FeatureServer.
        
        Returns:
            List of features with attributes and geometry
            
        Raises:
            Exception: If fetch fails
        """
        if not self.layer_url:
            raise ValueError("TII_ARCGIS_LAYER_URL not configured")
            
        try:
            query_url = f"{self.layer_url}/query"
            params = {
                'where': '1=1',
                'outFields': '*',
                'f': 'json',
                'returnGeometry': 'true',
                'outSR': '4326'  # WGS84
            }
            
            logger.info(f"Fetching TII features from {query_url}")
            response = requests.get(query_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            features = data.get('features', [])
            
            logger.info(f"Fetched {len(features)} camera features from TII")
            return features
            
        except Exception as e:
            logger.error(f"Failed to fetch TII features: {e}")
            raise
    
    def detect_snapshot_field(self, attributes: Dict[str, Any]) -> Optional[str]:
        """Auto-detect the attribute key containing snapshot URL.
        
        Args:
            attributes: Feature attributes dictionary
            
        Returns:
            Key name containing snapshot URL, or None if not found
        """
        # Common patterns for snapshot URL fields
        patterns = ['image', 'snapshot', 'url', 'photo', 'picture', 'jpeg', 'jpg']
        
        for key, value in attributes.items():
            if not isinstance(value, str):
                continue
                
            key_lower = key.lower()
            
            # Check if key matches common patterns
            if any(pattern in key_lower for pattern in patterns):
                # Validate it looks like a URL or image path
                if value.startswith('http') or value.endswith(('.jpg', '.jpeg', '.png')):
                    logger.info(f"Detected snapshot field: {key}")
                    return key
        
        logger.warning("No snapshot field detected in attributes")
        return None
    
    def download_snapshot(self, url: str, timeout: int = 10) -> bytes:
        """Download camera snapshot image.
        
        Args:
            url: Snapshot image URL
            timeout: Request timeout in seconds
            
        Returns:
            Image bytes
            
        Raises:
            Exception: If download fails
        """
        try:
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Read with size limit (1MB)
            content = response.content
            if len(content) > 1024 * 1024:
                raise ValueError(f"Image too large: {len(content)} bytes")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download snapshot from {url}: {e}")
            raise