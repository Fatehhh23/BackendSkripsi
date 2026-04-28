from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class EarthquakeData(BaseModel):
    """Schema untuk data gempa"""
    id: str
    magnitude: float
    depth: float  # km
    latitude: float
    longitude: float
    timestamp: datetime
    location: str
    source: str = "BMKG"  # BMKG or USGS
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "20251201-001",
                "magnitude": 5.8,
                "depth": 15.0,
                "latitude": -6.5,
                "longitude": 105.3,
                "timestamp": "2025-12-01T10:30:00",
                "location": "52 km Barat Daya Sumur-Banten",
                "source": "BMKG"
            }
        }

class EarthquakeResponse(BaseModel):
    """Response schema untuk data gempa"""
    status: str
    earthquakes: list[EarthquakeData]
    count: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
