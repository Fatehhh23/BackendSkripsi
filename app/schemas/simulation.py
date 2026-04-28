from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
from datetime import datetime

class SimulationRequest(BaseModel):
    """Request schema untuk simulasi tsunami"""
    magnitude: float = Field(..., ge=3.0, le=9.5, description="Magnitudo gempa")
    depth: float = Field(..., ge=1.0, le=700.0, description="Kedalaman gempa (km)")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    mode: str = Field("AI", description="Mode simulasi: 'AI' (Selat Sunda) atau 'HEURISTIC' (Umum)")
    
    @validator('magnitude')
    def validate_magnitude(cls, v):
        if not (3.0 <= v <= 9.5):
            raise ValueError('Magnitudo harus antara 3.0 dan 9.5')
        return v
    
    @validator('depth')
    def validate_depth(cls, v):
        if not (1.0 <= v <= 700.0):
            raise ValueError('Kedalaman harus antara 1 dan 700 km')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "magnitude": 7.5,
                "depth": 20.0,
                "latitude": -6.102,
                "longitude": 105.423
            }
        }

class ImpactZone(BaseModel):
    """Schema untuk zona terdampak"""
    name: str
    distance: float  # km dari epicenter
    eta: int  # menit
    waveHeight: float  # meter

class InundationZone(BaseModel):
    """Schema untuk zona genangan"""
    coordinates: List[List[List[float]]]  # GeoJSON polygon
    height: float  # meter

class Epicenter(BaseModel):
    """Schema untuk epicenter"""
    latitude: float
    longitude: float

class PredictionData(BaseModel):
    """Schema untuk data prediksi"""
    eta: int  # Estimated Time of Arrival (menit)
    maxWaveHeight: float  # meter
    affectedArea: float  # km²
    tsunamiCategory: str  # Low, Medium, High, Extreme
    estimatedCasualties: Optional[int] = 0

class WaveData(BaseModel):
    """Schema untuk data gelombang temporal"""
    time: int  # menit
    waveHeight: float  # meter

class SimulationResult(BaseModel):
    """Schema untuk hasil simulasi lengkap"""
    prediction: PredictionData
    epicenter: Epicenter
    inundationZones: List[InundationZone]
    impactZones: List[ImpactZone]
    waveData: List[WaveData]

class SimulationResponse(BaseModel):
    """Response schema untuk simulasi"""
    status: str
    data: SimulationResult
    message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": {
                    "prediction": {
                        "eta": 25,
                        "maxWaveHeight": 4.5,
                        "affectedArea": 120.5,
                        "tsunamiCategory": "High",
                        "estimatedCasualties": 500
                    },
                    "epicenter": {
                        "latitude": -6.102,
                        "longitude": 105.423
                    },
                    "inundationZones": [],
                    "impactZones": [
                        {
                            "name": "Pantai Anyer",
                            "distance": 25.0,
                            "eta": 20,
                            "waveHeight": 3.2
                        }
                    ],
                    "waveData": [
                        {"time": 0, "waveHeight": 0.5},
                        {"time": 5, "waveHeight": 1.2}
                    ]
                },
                "message": "Simulasi berhasil",
                "timestamp": "2025-12-01T00:00:00"
            }
        }
