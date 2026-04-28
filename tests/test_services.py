"""
Service Layer Tests
"""
import pytest
from app.services.geospatial_service import GeospatialService


@pytest.mark.asyncio
async def test_geospatial_service_distance():
    """Test geospatial distance calculation"""
    service = GeospatialService()
    
    # Test distance between two points
    point1 = (-6.102, 105.423)
    point2 = (-6.200, 105.500)
    
    distance = service.calculate_distance(point1, point2)
    
    # Distance should be positive
    assert distance > 0
    # Should be reasonable (in km)
    assert distance < 1000


@pytest.mark.asyncio
async def test_geospatial_service_bounds():
    """Test Sunda Strait boundary check"""
    service = GeospatialService()
    
    # Point inside Sunda Strait
    inside_point = (-6.102, 105.423)
    assert service.is_in_sunda_strait(inside_point[0], inside_point[1])
    
    # Point outside Sunda Strait
    outside_point = (-8.0, 110.0)
    assert not service.is_in_sunda_strait(outside_point[0], outside_point[1])


def test_config_loading():
    """Test that configuration loads correctly"""
    from app.config import settings
    
    assert settings.APP_NAME == "AVATAR Tsunami Prediction API"
    assert settings.VERSION is not None
    assert settings.MIN_MAGNITUDE > 0
    assert settings.MAX_MAGNITUDE > settings.MIN_MAGNITUDE
