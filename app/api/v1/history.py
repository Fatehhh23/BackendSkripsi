from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
import logging

from app.database.connection import get_db
from app.database import crud

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/simulation/history")
async def get_simulation_history(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", regex="^(created_at|magnitude)$"),
    order: str = Query(default="desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Mendapatkan riwayat simulasi yang pernah dijalankan.
    
    Parameters:
    - limit: Jumlah maksimum hasil (default: 10)
    - offset: Offset untuk pagination (default: 0)
    - sort_by: Field untuk sorting (created_at, magnitude)
    - order: Urutan sorting (asc, desc)
    """
    logger.info(f"Fetching simulation history: limit={limit}, offset={offset}")
    
    try:
        simulations = await crud.get_simulation_history(
            db=db,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order
        )
        
        total_count = await crud.count_simulations(db)
        
        return {
            "status": "success",
            "data": simulations,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching history: {e}", exc_info=True)
        return {
            "status": "error",
            "data": [],
            "message": str(e)
        }

@router.delete("/simulation/history/{simulation_id}")
async def delete_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Menghapus riwayat simulasi berdasarkan ID
    """
    try:
        success = await crud.delete_simulation(db, simulation_id)
        
        if success:
            return {
                "status": "success",
                "message": "Simulasi berhasil dihapus"
            }
        else:
            return {
                "status": "error",
                "message": "Simulasi tidak ditemukan"
            }
            
    except Exception as e:
        logger.error(f"Error deleting simulation: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

@router.get("/earthquakes/history")
async def get_earthquake_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Mendapatkan riwayat data gempa yang tersimpan
    """
    try:
        earthquakes = await crud.get_earthquake_history(db, limit, offset)
        total_count = await crud.count_earthquakes(db)
        
        return {
            "status": "success",
            "data": earthquakes,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching earthquake history: {e}", exc_info=True)
        return {
            "status": "error",
            "data": [],
            "message": str(e)
        }
