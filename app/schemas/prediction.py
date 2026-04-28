from pydantic import BaseModel
from typing import Dict, Any

class PredictionInput(BaseModel):
    """Input untuk model prediksi"""
    magnitude: float
    depth: float
    latitude: float
    longitude: float
    bathymetry_data: Dict[str, Any]
    topography_data: Dict[str, Any]

class ModelOutput(BaseModel):
    """Output dari model SSL-ViT-CNN"""
    tsunami_probability: float  # 0-1
    max_wave_height: float  # meter
    eta_seconds: int  # detik
    inundation_map: Dict[str, Any]  # GeoJSON
    confidence_score: float  # 0-1
