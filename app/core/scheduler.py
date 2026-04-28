import asyncio
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.earthquake_service import EarthquakeService
from app.database import crud
from app.database.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)

class EarthquakeScheduler:
    """
    Background scheduler to fetch earthquake data periodically.
    Uses asyncio.create_task instead of external libraries like APScheduler
    to keep dependencies minimal.
    """
    
    def __init__(self, interval_seconds: int = 300): # Default 5 minutes
        self.interval = interval_seconds
        self.is_running = False
        self._task = None
        self.earthquake_service = EarthquakeService()
        
    async def start(self):
        """Start the background scheduler"""
        if self.is_running:
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Earthquake scheduler started.")
        
    async def stop(self):
        """Stop the background scheduler"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Earthquake scheduler stopped.")
        
    async def _run_loop(self):
        """Main loop"""
        while self.is_running:
            try:
                await self.fetch_and_save_earthquakes()
            except Exception as e:
                logger.error(f"Error in earthquake scheduler loop: {e}", exc_info=True)
            
            # Wait for next interval
            await asyncio.sleep(self.interval)
            
    async def fetch_and_save_earthquakes(self):
        """Fetch data from APIs and save to database"""
        logger.info("Scheduler: Fetching real-time earthquake data...")
        
        # 1. Fetch from BMKG
        try:
            bmkg_data = await self.earthquake_service.fetch_recent_earthquakes(
                min_magnitude=2.0, 
                hours=24, 
                source="bmkg",
                limit=50
            )
            await self._save_batch(bmkg_data)
            logger.info(f"Scheduler: Fetched {len(bmkg_data)} quakes from BMKG")
        except Exception as e:
            logger.error(f"Scheduler failed to fetch from BMKG: {e}")
            
        # 2. Fetch from USGS
        try:
            usgs_data = await self.earthquake_service.fetch_recent_earthquakes(
                min_magnitude=4.5, 
                hours=24, 
                source="usgs",
                limit=50
            )
            await self._save_batch(usgs_data)
            logger.info(f"Scheduler: Fetched {len(usgs_data)} quakes from USGS")
        except Exception as e:
            logger.error(f"Scheduler failed to fetch from USGS: {e}")
            
    async def _save_batch(self, earthquakes: List[dict]):
        """Save a batch of earthquakes to database"""
        if not earthquakes:
            return
            
        # Use a new session for this batch
        async with AsyncSessionLocal() as db:
            count = 0
            for eq_data in earthquakes:
                try:
                    # Check if exists
                    existing = await crud.get_earthquake_by_id(db, eq_data['id'])
                    if not existing:
                        await crud.save_earthquake_data(db, eq_data)
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to save earthquake {eq_data.get('id')}: {e}")
                    continue
            
            if count > 0:
                logger.info(f"Scheduler: Saved {count} new earthquakes to database")

# Global instance
scheduler = EarthquakeScheduler()
