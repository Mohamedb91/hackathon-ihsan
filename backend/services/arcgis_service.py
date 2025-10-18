import requests
import logging
import re
from typing import List, Dict, Any, Optional
from core.config import config

logger = logging.getLogger(__name__)

class TIIValidationStatus:
    """Singleton to hold TII validation state."""
    def __init__(self):
        self.enabled = config.TII_ENABLE
        self.validated = False
        self.validation_error: Optional[str] = None
    
    def set_validated(self, success: bool, error: Optional[str] = None):
        self.validated = success
        self.validation_error = error

# Global singleton instance
tii_status = TIIValidationStatus()

class ArcGISService:
    """Service for fetching TII camera data from ArcGIS REST API."""
    
    def __init__(self):
        self.layer_url = config.TII_ARCGIS_LAYER_URL
        self.snapshot_field_override = config.TII_SNAPSHOT_FIELD
        
    def validate_layer_url(self) -> bool:
        """Validate the ArcGIS FeatureServer layer URL.
        
        Returns:
            True if valid, False otherwise. Updates global tii_status.
        """
        if not config.TII_ENABLE:
            tii_status.set_validated(False, "TII disabled by configuration (TII_ENABLE=false)")
            logger.info("TII integration disabled by config")
            return False
            
        if not self.layer_url:
            tii_status.set_validated(False, "TII_ARCGIS_LAYER_URL not configured in .env")
            logger.warning("TII_ARCGIS_LAYER_URL not configured")
            return False
            
        try:
            query_url = f"{self.layer_url}/query"
            params = {
                'where': '1=1',
                'outFields': '*',
                'returnGeometry': 'true',
                'f': 'json'
            }
            
            logger.info(f"Validating TII ArcGIS layer: {query_url}")
            response = requests.get(query_url, params=params, timeout=(5, 10))
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                error_msg = f"ArcGIS API error: {data['error'].get('message', 'Unknown error')}"
                tii_status.set_validated(False, error_msg)
                logger.error(f"ERROR: TII validation failed: {error_msg}. Integration disabled. Provide a FeatureServer layer URL (.../FeatureServer/0).")
                return False
            
            features = data.get('features', [])
            if not features:
                error_msg = (
                    "Invalid ArcGIS FeatureServer layer. No features returned. "
                    "Provide a valid FeatureServer layer root URL (e.g., https://example.com/FeatureServer/0)."
                )
                tii_status.set_validated(False, error_msg)
                logger.error(f"ERROR: TII validation failed: {error_msg}. Integration disabled.")
                return False
            
            logger.info(f"✓ TII ArcGIS layer validated successfully ({len(features)} features found)")
            tii_status.set_validated(True, None)
            return True
            
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout connecting to ArcGIS layer (5s connect, 10s read): {self.layer_url}"
            tii_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TII validation failed: {error_msg}. Integration disabled. Provide a FeatureServer layer URL (.../FeatureServer/0).")
            return False
        except requests.exceptions.ConnectionError as e:
            error_msg = f"DNS resolution or network error connecting to ArcGIS layer: {str(e)[:200]}"
            tii_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TII validation failed: {error_msg}. Integration disabled. Provide a FeatureServer layer URL (.../FeatureServer/0).")
            return False
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to ArcGIS layer: {str(e)[:200]}"
            tii_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TII validation failed: {error_msg}. Integration disabled. Provide a FeatureServer layer URL (.../FeatureServer/0).")
            return False
        except Exception as e:
            error_msg = f"Unexpected error validating layer: {str(e)[:200]}"
            tii_status.set_validated(False, error_msg)
            logger.error(f"ERROR: TII validation failed: {error_msg}. Integration disabled.", exc_info=True)
            return False
        
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
            response = requests.get(query_url, params=params, timeout=(5, 30))
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                raise Exception(f"ArcGIS API error: {data['error'].get('message', 'Unknown error')}")
            
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
        # If override is set, check if it exists
        if self.snapshot_field_override:
            if self.snapshot_field_override in attributes:
                value = attributes[self.snapshot_field_override]
                if self._is_valid_snapshot_url(value):
                    logger.info(f"Using override snapshot field: {self.snapshot_field_override}")
                    return self.snapshot_field_override
                else:
                    logger.warning(f"Override field '{self.snapshot_field_override}' found but value doesn't look like image URL: {value}")
        
        # Auto-detect pattern
        pattern = re.compile(r'(image|snapshot|url|photo|picture|jpeg|jpg|camera)', re.IGNORECASE)
        url_pattern = re.compile(r'^https?://.*\.(jpg|jpeg|png)(\?.*)?$', re.IGNORECASE)
        
        for key, value in attributes.items():
            if not isinstance(value, str):
                continue
            
            # Check if key matches pattern
            if pattern.search(key):
                # Validate URL format
                if url_pattern.match(value) or (value.startswith('http') and any(ext in value.lower() for ext in ['.jpg', '.jpeg', '.png'])):
                    logger.info(f"Auto-detected snapshot field: {key}")
                    return key
        
        logger.warning("No snapshot field detected in attributes")
        return None
    
    def _is_valid_snapshot_url(self, value: str) -> bool:
        """Check if value looks like a valid snapshot URL.
        
        Args:
            value: String value to check
            
        Returns:
            True if looks like image URL
        """
        if not isinstance(value, str):
            return False
        
        url_pattern = re.compile(r'^https?://.*\.(jpg|jpeg|png)(\?.*)?$', re.IGNORECASE)
        return bool(url_pattern.match(value)) or (value.startswith('http') and any(ext in value.lower() for ext in ['.jpg', '.jpeg', '.png']))
    
    def download_snapshot(self, url: str) -> bytes:
        """Download camera snapshot image.
        
        Args:
            url: Snapshot image URL
            
        Returns:
            Image bytes
            
        Raises:
            Exception: If download fails
        """
        try:
            response = requests.get(url, timeout=(5, 10), stream=True)
            response.raise_for_status()
            
            # Read with size limit (1MB)
            content = response.content
            if len(content) > 1024 * 1024:
                raise ValueError(f"Image too large: {len(content)} bytes")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download snapshot from {url}: {e}")
            raise