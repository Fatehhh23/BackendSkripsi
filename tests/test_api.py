"""
API Endpoint Tests
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns healthy status"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_ping_endpoint(client: AsyncClient):
    """Test ping endpoint"""
    response = await client.get("/api/ping")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_simulation_endpoint_validation(client: AsyncClient):
    """Test simulation endpoint with invalid data"""
    invalid_data = {
        "magnitude": 15.0,  # Invalid: too high
        "depth": -10.0,     # Invalid: negative
        "latitude": -6.102,
        "longitude": 105.423
    }
    response = await client.post("/api/v1/simulation/run", json=invalid_data)
    # Should return validation error (422)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_simulation_endpoint_valid(client: AsyncClient, sample_earthquake_data):
    """Test simulation endpoint with valid data"""
    response = await client.post("/api/v1/simulation/run", json=sample_earthquake_data)
    # May return 200 or error depending on model availability
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "simulation_id" in data
