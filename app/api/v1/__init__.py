from fastapi import APIRouter

# Import routers
from app.api.v1 import auth, health, simulation, history, realtime, admin

api_router = APIRouter()

# Register all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])
api_router.include_router(history.router, prefix="/history", tags=["History"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["Real-time Data"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

