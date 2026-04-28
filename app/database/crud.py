from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, delete
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from app.database.models import Simulation, Earthquake, InundationZone, User, UserRole
# from geoalchemy2.shape import from_shape  # TEMP: Commented out - requires GDAL/PROJ libraries
# from shapely.geometry import Point  # TEMP: Commented out - requires GDAL/PROJ libraries

logger = logging.getLogger(__name__)

# ========== SIMULATION CRUD ==========

async def save_simulation_result(
    db: AsyncSession,
    params: Dict[str, Any],
    result: Dict[str, Any],
    processing_time_ms: Optional[int] = None,
    user_session_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    mode: str = "AI"
) -> Simulation:
    """
    Menyimpan hasil simulasi ke database
    """
    try:
        # Create Point geometry for epicenter
        # TEMP: Commented out - requires geoalchemy2
        # point = Point(params['longitude'], params['latitude'])
        
        # Check if we need to auto-create or assign a Guest user
        if not user_id and user_session_id:
            # Look for existing guest by username matching session id
            user_query = await db.execute(select(User).where(User.username == user_session_id))
            guest_user = user_query.scalar_one_or_none()
            
            if not guest_user:
                # Create a new guest user
                guest_user = User(
                    email=f"{user_session_id}@guest.local",
                    username=user_session_id,
                    password_hash="guest_no_login_allowed_hash_dummy",
                    full_name=f"Guest User",
                    role=UserRole.GUEST,
                    is_active=True,
                    is_verified=True
                )
                db.add(guest_user)
                await db.commit()
                await db.refresh(guest_user)
            
            # Map the simulation to this guest user
            user_id = guest_user.id

        simulation = Simulation(
            magnitude=params['magnitude'],
            depth=params['depth'],
            latitude=params['latitude'],
            longitude=params['longitude'],
            mode=mode,
            # TEMP: Commented out - requires geoalchemy2
            # epicenter=from_shape(point, srid=4326),
            prediction_data=result,
            processing_time_ms=processing_time_ms,
            user_session_id=user_session_id,
            user_id=user_id,
            ip_address=ip_address,
            model_version="1.0.0"
        )
        
        db.add(simulation)
        await db.commit()
        await db.refresh(simulation)
        
        logger.info(f"Saved simulation {simulation.id}")
        return simulation
        
    except Exception as e:
        logger.error(f"Error saving simulation: {e}", exc_info=True)
        await db.rollback()
        raise

async def get_simulation_by_id(db: AsyncSession, simulation_id: str) -> Optional[Dict]:
    """
    Mendapatkan simulasi berdasarkan ID
    """
    try:
        result = await db.execute(
            select(Simulation).where(Simulation.id == uuid.UUID(simulation_id))
        )
        simulation = result.scalar_one_or_none()
        
        if simulation:
            return {
                "id": str(simulation.id),
                "magnitude": simulation.magnitude,
                "depth": simulation.depth,
                "latitude": simulation.latitude,
                "longitude": simulation.longitude,
                "prediction_data": simulation.prediction_data,
                "created_at": simulation.created_at.isoformat(),
                "processing_time_ms": simulation.processing_time_ms,
                "mode": simulation.mode
            }
        return None
        
    except Exception as e:
        logger.error(f"Error fetching simulation: {e}", exc_info=True)
        return None

async def get_simulation_history(
    db: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    order: str = "desc"
) -> List[Dict]:
    """
    Mendapatkan riwayat simulasi dengan pagination
    """
    try:
        # Build query
        query = select(Simulation)
        
        # Add sorting
        if order == "desc":
            query = query.order_by(desc(getattr(Simulation, sort_by)))
        else:
            query = query.order_by(asc(getattr(Simulation, sort_by)))
        
        # Add pagination
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        simulations = result.scalars().all()
        
        return [
            {
                "id": str(sim.id),
                "magnitude": sim.magnitude,
                "depth": sim.depth,
                "latitude": sim.latitude,
                "longitude": sim.longitude,
                "created_at": sim.created_at.isoformat(),
                "tsunami_category": sim.prediction_data.get('prediction', {}).get('tsunamiCategory', 'Unknown'),
                "mode": sim.mode
            }
            for sim in simulations
        ]
        
    except Exception as e:
        logger.error(f"Error fetching history: {e}", exc_info=True)
        return []

async def count_simulations(db: AsyncSession) -> int:
    """
    Menghitung total simulasi
    """
    result = await db.execute(select(func.count(Simulation.id)))
    return result.scalar() or 0

async def delete_simulation(db: AsyncSession, simulation_id: str) -> bool:
    """
    Menghapus simulasi berdasarkan ID
    """
    try:
        result = await db.execute(
            select(Simulation).where(Simulation.id == uuid.UUID(simulation_id))
        )
        simulation = result.scalar_one_or_none()
        
        if simulation:
            await db.delete(simulation)
            await db.commit()
            return True
        return False
        
    except Exception as e:
        logger.error(f"Error deleting simulation: {e}", exc_info=True)
        await db.rollback()
        return False

# ========== EARTHQUAKE CRUD ==========

async def save_earthquake_data(db: AsyncSession, earthquake: Dict[str, Any]) -> Earthquake:
    """
    Menyimpan data gempa ke database
    """
    try:
        # Check if already exists
        result = await db.execute(
            select(Earthquake).where(Earthquake.id == earthquake['id'])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing
        
        # Create new record
        # TEMP: Commented out - requires geoalchemy2
        # point = Point(earthquake['longitude'], earthquake['latitude'])
        
        eq = Earthquake(
            id=earthquake['id'],
            magnitude=earthquake['magnitude'],
            depth=earthquake['depth'],
            latitude=earthquake['latitude'],
            longitude=earthquake['longitude'],
            # TEMP: Commented out - requires geoalchemy2
            # location=from_shape(point, srid=4326),
            location_name=earthquake.get('location', ''),
            timestamp=earthquake['timestamp'],
            source=earthquake.get('source', 'BMKG')
        )
        
        db.add(eq)
        await db.commit()
        await db.refresh(eq)
        
        return eq
        
    except Exception as e:
        logger.error(f"Error saving earthquake: {e}", exc_info=True)
        await db.rollback()
        raise

async def get_earthquake_by_id(db: AsyncSession, earthquake_id: str) -> Optional[Dict]:
    """
    Mendapatkan data gempa berdasarkan ID
    """
    try:
        result = await db.execute(
            select(Earthquake).where(Earthquake.id == earthquake_id)
        )
        eq = result.scalar_one_or_none()
        
        if eq:
            return {
                "id": eq.id,
                "magnitude": eq.magnitude,
                "depth": eq.depth,
                "latitude": eq.latitude,
                "longitude": eq.longitude,
                "location": eq.location_name,
                "timestamp": eq.timestamp.isoformat(),
                "source": eq.source
            }
        return None
        
    except Exception as e:
        logger.error(f"Error fetching earthquake: {e}", exc_info=True)
        return None

async def get_earthquake_history(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    Mendapatkan riwayat gempa
    """
    try:
        result = await db.execute(
            select(Earthquake)
            .order_by(desc(Earthquake.timestamp))
            .limit(limit)
            .offset(offset)
        )
        earthquakes = result.scalars().all()
        
        return [
            {
                "id": eq.id,
                "magnitude": eq.magnitude,
                "depth": eq.depth,
                "latitude": eq.latitude,
                "longitude": eq.longitude,
                "location": eq.location_name,
                "timestamp": eq.timestamp.isoformat(),
                "source": eq.source
            }
            for eq in earthquakes
        ]
        
    except Exception as e:
        logger.error(f"Error fetching earthquake history: {e}", exc_info=True)
        return []

async def count_earthquakes(db: AsyncSession) -> int:
    """
    Menghitung total data gempa
    """
    return result.scalar() or 0

async def delete_user_simulation_history(db: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Menghapus semua riwayat simulasi milik user tertentu
    """
    try:
        stmt = delete(Simulation).where(Simulation.user_id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    except Exception as e:
        logger.error(f"Error deleting user history: {e}", exc_info=True)
        await db.rollback()
        raise
