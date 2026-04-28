from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import health, simulation, realtime, history, auth, admin, contacts
from app.core.scheduler import scheduler
from app.database.connection import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    await init_db()
    # Startup: Start scheduler
    await scheduler.start()
    yield
    # Shutdown: Stop scheduler
    await scheduler.stop()

# ============================================
# FastAPI App Instance
# ============================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description="WebGIS Simulasi Prediksi Tsunami Selat Sunda dengan SSL-ViT-CNN",
    lifespan=lifespan,
)

# ============================================
# CORS Middleware
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Root Endpoint
# ============================================
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "AVATAR Tsunami Prediction API is running",
        "version": settings.VERSION,
        "status": "healthy",
    }

# ============================================
# Include All Routers
# ============================================
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(simulation.router, prefix="/api/v1/simulation", tags=["Simulation"])
app.include_router(realtime.router, prefix="/api/v1/earthquakes", tags=["Real-Time"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["Contacts"])
