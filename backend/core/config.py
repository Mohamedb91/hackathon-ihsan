import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

class Config:
    """Application configuration."""
    
    # Gemini settings
    GEMINI_API_KEY: str = os.environ.get('EMERGENT_LLM_KEY', '')
    GEMINI_VISION_MODEL: str = os.environ.get('GEMINI_VISION_MODEL', 'gemini-2.0-flash')
    
    # Server settings
    HOST: str = os.environ.get('HOST', '0.0.0.0')
    PORT: int = int(os.environ.get('PORT', 8001))
    
    # MongoDB settings
    MONGO_URL: str = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    DB_NAME: str = os.environ.get('DB_NAME', 'civicflow')
    
    # CORS settings
    CORS_ORIGINS: str = os.environ.get('CORS_ORIGINS', '*')
    
    # TII Camera Integration
    TII_ENABLE: bool = os.environ.get('TII_ENABLE', 'true').lower() in ('true', '1', 'yes')
    TII_ARCGIS_LAYER_URL: str = os.environ.get('TII_ARCGIS_LAYER_URL', '')
    TII_SNAPSHOT_FIELD: str = os.environ.get('TII_SNAPSHOT_FIELD', '')
    TII_POLL_INTERVAL_MIN: int = int(os.environ.get('TII_POLL_INTERVAL_MIN', 15))
    MAX_CAMERAS_PER_CYCLE: int = int(os.environ.get('MAX_CAMERAS_PER_CYCLE', 100))
    
    # TfL JamCams Integration
    TFL_ENABLE: bool = os.environ.get('TFL_ENABLE', 'false').lower() in ('true', '1', 'yes')
    TFL_BASE: str = os.environ.get('TFL_BASE', 'https://api.tfl.gov.uk')
    TFL_APP_ID: str = os.environ.get('TFL_APP_ID', '')
    TFL_APP_KEY: str = os.environ.get('TFL_APP_KEY', '')
    TFL_POLL_INTERVAL_MIN: int = int(os.environ.get('TFL_POLL_INTERVAL_MIN', 3))
    TFL_MAX_CAMERAS_PER_CYCLE: int = int(os.environ.get('TFL_MAX_CAMERAS_PER_CYCLE', 150))
    TFL_HTTP_TIMEOUT_CONNECT_S: int = int(os.environ.get('TFL_HTTP_TIMEOUT_CONNECT_S', 5))
    TFL_HTTP_TIMEOUT_READ_S: int = int(os.environ.get('TFL_HTTP_TIMEOUT_READ_S', 10))
    TFL_SEED_FILE: str = os.environ.get('TFL_SEED_FILE', '/app/data/tfl_cameras_seed.json')

config = Config()