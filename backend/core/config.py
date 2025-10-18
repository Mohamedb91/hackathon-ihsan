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
    TII_ARCGIS_LAYER_URL: str = os.environ.get('TII_ARCGIS_LAYER_URL', '')
    TII_SNAPSHOT_FIELD: str = os.environ.get('TII_SNAPSHOT_FIELD', '')
    TII_POLL_INTERVAL_MIN: int = int(os.environ.get('TII_POLL_INTERVAL_MIN', 15))
    MAX_CAMERAS_PER_CYCLE: int = int(os.environ.get('MAX_CAMERAS_PER_CYCLE', 100))

config = Config()