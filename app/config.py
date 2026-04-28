from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict
import os
from pathlib import Path


class Settings(BaseSettings):
    # ============================================
    # Application Settings
    # ============================================
    APP_NAME: str = "AVATAR Tsunami Prediction API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ============================================
    # CORS Settings
    # ============================================
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # ============================================
    # Database Settings
    # ============================================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:AVATAR23@localhost:5432/tsunamidb"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # ============================================
    # PostGIS
    # ============================================
    POSTGIS_VERSION: str = "3.3"
    
    # ============================================
    # Model Configuration (PyTorch)
    # ============================================
    MODEL_RESNET_PATH: str = "trained_models/pi_resnet50.pth"
    MODEL_MMVIT_PATH: str = "trained_models/pi_mmvit.pth"
    MODEL_CONFIG_PATH: str = "trained_models/model_config.json"
    USE_GPU: bool = False
    BATCH_SIZE: int = 1
    
    # ============================================
    # Data Paths
    # ============================================
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    BATHYMETRY_DIR: Path = DATA_DIR / "bathymetry"
    TOPOGRAPHY_DIR: Path = DATA_DIR / "topography"
    COASTLINES_DIR: Path = DATA_DIR / "coastlines"
    DEM_GEOTIFF_PATH: str = "data/dem/DEM_TopoBathy_Selat_Sunda_30m.tif"
    
    # ============================================
    # External API
    # ============================================
    BMKG_API_URL: str = "https://data.bmkg.go.id/DataMKG/TEWS/"
    USGS_API_URL: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    API_TIMEOUT: int = 30
    
    # ============================================
    # Real-Time Monitoring
    # ============================================
    ENABLE_REALTIME_MONITORING: bool = True
    POLL_INTERVAL: int = 60  # seconds
    
    # ============================================
    # Simulation Parameters
    # ============================================
    MIN_MAGNITUDE: float = 3.0
    MAX_MAGNITUDE: float = 9.5
    MIN_DEPTH: float = 1.0
    MAX_DEPTH: float = 700.0
    
    # ============================================
    # Selat Sunda Boundaries
    # ============================================
    SUNDA_STRAIT_BOUNDS: Dict[str, float] = {
        "min_lat": -7.0,
        "max_lat": -5.0,
        "min_lon": 104.5,
        "max_lon": 106.5
    }
    
    # ============================================
    # Cache Settings
    # ============================================
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 300  # seconds
    
    # ============================================
    # Rate Limiting
    # ============================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # seconds
    
    # ============================================
    # Logging
    # ============================================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/avatar_backend.log"
    
    # ✅ FIXED: Pydantic v2 menggunakan model_config, bukan class Config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields dari .env
    )


# Singleton instance
settings = Settings()