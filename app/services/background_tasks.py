import asyncio
import logging
from datetime import datetime

from app.services.earthquake_service import EarthquakeService
from app.config import settings

logger = logging.getLogger(__name__)

_monitoring_task = None

async def start_background_monitor():
    """
    Start background task untuk monitoring gempa real-time
    """
    global _monitoring_task
    
    if not settings.ENABLE_REALTIME_MONITORING:
        logger.info("Real-time monitoring is disabled")
        return
    
    logger.info("Starting background earthquake monitoring...")
    _monitoring_task = asyncio.create_task(monitor_earthquakes())

async def stop_background_monitor():
    """
    Stop background monitoring task
    """
    global _monitoring_task
    
    if _monitoring_task:
        _monitoring_task.cancel()
        try:
            await _monitoring_task
        except asyncio.CancelledError:
            logger.info("Background monitoring stopped")

async def monitor_earthquakes():
    """
    Background task to periodically fetch earthquake data
    """
    earthquake_service = EarthquakeService()
    
    while True:
        try:
            logger.info("[Background] Fetching latest earthquakes...")
            
            earthquakes = await earthquake_service.fetch_recent_earthquakes(
                min_magnitude=5.0,
                hours=24,
                limit=10
            )
            
            if earthquakes:
                logger.info(f"[Background] Found {len(earthquakes)} earthquakes")
                
                # Check for high-risk earthquakes
                for eq in earthquakes:
                    if eq['magnitude'] >= 7.0 and eq['depth'] < 50:
                        logger.warning(
                            f"⚠️ HIGH RISK EARTHQUAKE DETECTED: "
                            f"M{eq['magnitude']} at ({eq['latitude']}, {eq['longitude']})"
                        )
                        # TODO: Trigger automatic prediction
                        # TODO: Send alert notifications
            
            # Sleep until next poll
            await asyncio.sleep(settings.POLL_INTERVAL)
            
        except asyncio.CancelledError:
            logger.info("Background monitoring cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background monitoring: {e}", exc_info=True)
            # Sleep before retry
            await asyncio.sleep(60)
