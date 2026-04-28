"""
Pytest configuration and fixtures
"""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
async def client():
    """
    Async test client fixture
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_earthquake_data():
    """
    Sample earthquake data for testing
    """
    return {
        "magnitude": 7.5,
        "depth": 20.0,
        "latitude": -6.102,
        "longitude": 105.423
    }


@pytest.fixture
def sample_simulation_response():
    """
    Sample simulation response for testing
    """
    return {
        "simulation_id": "test-uuid-123",
        "magnitude": 7.5,
        "depth": 20.0,
        "epicenter": {
            "latitude": -6.102,
            "longitude": 105.423
        },
        "prediction": {
            "tsunami_risk": "high",
            "estimated_height": 5.2,
            "affected_areas": ["Anyer", "Carita"]
        }
    }
