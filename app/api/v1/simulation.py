from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.schemas.simulation import SimulationRequest, SimulationResponse
from app.services.prediction_service import prediction_service
from app.database.connection import get_db
from app.database import crud
from app.utils.validators import validate_earthquake_params
from app.core.dependencies import get_current_user_optional
from app.database.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/simulation/run", response_model=SimulationResponse)
async def run_simulation(
    request_data: SimulationRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_session_id: Optional[str] = Header(None)
):
    """
    Endpoint untuk menjalankan simulasi tsunami manual.
    
    Parameters:
    - magnitude: Magnitudo gempa (3.0 - 9.5)
    - depth: Kedalaman gempa dalam km (1 - 700)
    - latitude: Koordinat lintang (-90 to 90)
    - longitude: Koordinat bujur (-180 to 180)
    
    Returns:
    - Hasil prediksi tsunami termasuk ETA, tinggi gelombang, zona genangan
    """
    logger.info(f"Simulation request: M{request_data.magnitude} at ({request_data.latitude}, {request_data.longitude})")
    
    # Validate input parameters
    try:
        validate_earthquake_params(
            request_data.magnitude,
            request_data.depth,
            request_data.latitude,
            request_data.longitude
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # ============================================================
    # ACCESS CONTROL: AI Mode is now accessible to all users (guests)
    # ============================================================
    # The previous auth requirement has been removed as per user request.

    try:
        # Run prediction (menggunakan singleton — model sudah di-load saat startup)
        result = await prediction_service.predict(
            magnitude=request_data.magnitude,
            depth=request_data.depth,
            latitude=request_data.latitude,
            longitude=request_data.longitude,
            mode=request_data.mode
        )
        
        # Get client IP address
        client_ip = req.client.host if req.client else None
        
        # Get processing time from result
        processing_time_ms = result.get('prediction', {}).get('processingTimeMs', None)
        
        # Save to database synchronously to ensure it's saved before session closes
        try:
            await crud.save_simulation_result(
                db=db,
                params=request_data.dict(),
                result=result,
                processing_time_ms=processing_time_ms,
                user_session_id=x_session_id,
                user_id=current_user.id if current_user else None,
                ip_address=client_ip,
                mode=request_data.mode
            )
        except Exception as save_error:
            logger.error(f"Failed to save simulation result: {save_error}")
            # Don't fail the whole request if saving fails, but log it

        
        logger.info(f"Simulation completed: ETA={result['prediction']['eta']}min")
        
        return SimulationResponse(
            status="success",
            data=result,
            message="Simulasi berhasil dijalankan"
        )
        
    except Exception as e:
        logger.error(f"Simulation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menjalankan simulasi: {str(e)}"
        )

@router.get("/simulation/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Mendapatkan detail simulasi berdasarkan ID
    """
    simulation = await crud.get_simulation_by_id(db, simulation_id)
    
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulasi tidak ditemukan")
    
    return {
        "status": "success",
        "data": simulation
    }
