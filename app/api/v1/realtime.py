from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timedelta
import logging

from app.services.earthquake_service import EarthquakeService
from app.database.connection import get_db
from app.database import crud

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/realtime")
async def get_realtime_earthquakes(
    limit: int = Query(default=50, ge=1, le=100),
    min_magnitude: Optional[float] = Query(default=2.0, ge=1.0),
    hours: int = Query(default=24, ge=1, le=168),  # Max 1 week
    db: AsyncSession = Depends(get_db)
):
    """
    Mendapatkan data gempa real-time dari BMKG/USGS.
    
    Parameters:
    - limit: Jumlah maksimum data gempa (default: 10)
    - min_magnitude: Magnitudo minimum (default: 5.0)
    - hours: Rentang waktu dalam jam (default: 24)
    """
    logger.info(f"Serving realtime earthquakes from DB: limit={limit}")
    
    try:
        # Get from database (populated by scheduler)
        earthquakes = await crud.get_earthquake_history(db, limit=limit)
        
        # Use the singleton Prediction Service (AI Model)
        from app.services.prediction_service import prediction_service
        model_active = prediction_service.model_loaded
        if not model_active:
            logger.warning("PredictionService was not fully loaded (models failed)")


        # Analyze tsunami risk for each earthquake
        analyzed_earthquakes = []
        for eq in earthquakes:
            risk_level = "Rendah"
            max_wave_height = 0.0
            
            if model_active:
                try:
                    # Run AI Prediction
                    # Ensure parameters are floats
                    pred_result = await prediction_service.predict(
                        magnitude=float(eq['magnitude']),
                        depth=float(eq['depth']),
                        latitude=float(eq['latitude']),
                        longitude=float(eq['longitude'])
                    )
                    
                    # Extract result
                    prediction = pred_result.get('prediction', {})
                    model_category = prediction.get('tsunamiCategory', 'Low')
                    max_wave_height = prediction.get('maxWaveHeight', 0.0)
                    
                    # Map Category to Indonesian (Bahaya/Sedang/Rendah)
                    if model_category in ['Extreme', 'High']:
                        risk_level = "Bahaya"
                    elif model_category == 'Medium':
                        risk_level = "Sedang"
                    else:
                        risk_level = "Rendah"
                        
                except Exception as pred_error:
                    logger.warning(f"AI Prediction failed for EQ {eq.get('id')}: {pred_error}")
                    # Fallback to heuristic if AI fails
                    if eq['magnitude'] >= 7.5 and eq['depth'] < 50:
                        risk_level = "Bahaya"
                        max_wave_height = (float(eq['magnitude']) - 6.5) * 2
                    elif eq['magnitude'] >= 7.0 and eq['depth'] < 70:
                        risk_level = "Sedang"
                        max_wave_height = (float(eq['magnitude']) - 6.0) * 1.5
            
            else:
                 # Fallback (Original Heuristic)
                if eq['magnitude'] >= 7.5 and eq['depth'] < 50:
                    risk_level = "Bahaya"
                    max_wave_height = (float(eq['magnitude']) - 6.5) * 2
                elif eq['magnitude'] >= 7.0 and eq['depth'] < 70:
                    risk_level = "Sedang"
                    max_wave_height = (float(eq['magnitude']) - 6.0) * 1.5
            
            # Add risk info
            eq["riskLevel"] = risk_level
            eq["maxWaveHeight"] = round(max_wave_height, 2)
            analyzed_earthquakes.append(eq)
        
        return {
            "status": "success",
            "earthquakes": analyzed_earthquakes,
            "count": len(analyzed_earthquakes),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error serving realtime data: {e}", exc_info=True)
        return {
            "status": "error",
            "earthquakes": [],
            "message": str(e)
        }

@router.get("/earthquakes/{earthquake_id}")
async def get_earthquake_detail(
    earthquake_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Mendapatkan detail gempa berdasarkan ID
    """
    earthquake = await crud.get_earthquake_by_id(db, earthquake_id)
    
    if not earthquake:
        return {
            "status": "error",
            "message": "Data gempa tidak ditemukan"
        }
    
    return {
        "status": "success",
        "data": earthquake
    }
