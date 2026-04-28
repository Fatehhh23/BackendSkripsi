# AVATAR Backend - Tsunami Prediction System

Backend API untuk WebGIS Simulasi Prediksi Tsunami Selat Sunda dengan integrasi model **Physics-Informed Multi-Modal Vision Transformer (PI-MMViT)** dan **Physics-Informed ResNet-50 (PI-ResNet50)**.

## 📦 Tech Stack

### Core Framework
- **FastAPI 0.109** - Modern, high-performance web framework
- **Uvicorn** - ASGI server dengan async support
- **Pydantic v2** - Data validation dan settings management

### Database
- **PostgreSQL 15** - Relational database
- **PostGIS 3.3** - Spatial database extension
- **SQLAlchemy 2.0** - Async ORM
- **Alembic** - Database migration tool
- **GeoAlchemy2** - Geospatial types for SQLAlchemy

### Geospatial Processing
- **GeoPandas** - Geospatial data manipulation
- **Shapely** - Geometric operations
- **Rasterio** - Raster data I/O
- **Fiona** - Vector data I/O
- **PyProj** - Cartographic projections
- **Geopy** - Geocoding and distance calculations

### Machine Learning
- **PyTorch 2.11** - Deep learning framework (inference & training)
- **TorchVision** - Model ResNet-50 pretrained ImageNet
- **NumPy** - Numerical computing
- **scikit-image** - Kontur inundasi (Marching Squares)

### External APIs
- **aiohttp** - Async HTTP client
- **httpx** - Modern HTTP client

## 📁 Project Structure

```
BackendSkripsi/
├── app/
│   ├── api/v1/              # API endpoints
│   │   ├── simulation.py    # Simulasi manual
│   │   ├── realtime.py      # Monitoring real-time BMKG/USGS
│   │   ├── history.py       # Riwayat simulasi
│   │   ├── health.py        # Health check
│   │   ├── auth.py          # Autentikasi (JWT)
│   │   ├── admin.py         # Admin management
│   │   └── contacts.py      # Form kontak
│   ├── database/            # Database layer
│   │   ├── connection.py    # SQLAlchemy async setup
│   │   ├── models.py        # ORM models (PostGIS)
│   │   └── crud.py          # CRUD operations
│   ├── schemas/             # Pydantic schemas
│   │   ├── simulation.py    # Request/Response simulasi
│   │   ├── auth.py          # Auth schemas
│   │   └── earthquake.py    # Earthquake schemas
│   ├── services/            # Business logic
│   │   ├── prediction_service.py   # Prediksi tsunami (AI + Heuristic)
│   │   ├── model_architecture.py   # Arsitektur PI-ResNet50 & PI-MMViT
│   │   ├── earthquake_service.py   # Data gempa real-time
│   │   ├── geospatial_service.py   # Pengolahan geospasial
│   │   ├── auth_service.py         # Autentikasi & JWT
│   │   └── background_tasks.py     # Scheduler tasks
│   ├── core/                # Middleware & dependencies
│   ├── utils/               # Utilities & validators
│   ├── main.py              # FastAPI app entry
│   └── config.py            # Configuration (PyTorch paths)
├── trained_models/          # Model weights (.pth)
│   ├── pi_resnet50.pth      # PI-ResNet50 (51M params)
│   └── pi_mmvit.pth         # PI-MMViT (5.4M params)
├── data/                    # Data assets (DEM, coastlines)
├── tests/                   # Unit tests
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── start_avatar.bat         # Quick start script
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with PostGIS
- Docker & Docker Compose (optional)

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/Fatehhh23/Backend---Skripsi-.git
cd Backend---Skripsi-

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f backend

# API akan tersedia di:
# - Backend: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - pgAdmin: http://localhost:5050
```

### Option 2: Manual Setup

#### 1. Install PostgreSQL + PostGIS

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql-15 postgresql-15-postgis-3
```

**macOS:**
```bash
brew install postgresql postgis
```

**Windows:**
Download installer dari [PostgreSQL](https://www.postgresql.org/download/windows/) dan [PostGIS](https://postgis.net/install/)

#### 2. Create Database

```bash
# Login ke PostgreSQL
psql -U postgres

# Create database dan user
CREATE DATABASE tsunami_db;
CREATE USER tsunami_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tsunami_db TO tsunami_user;

# Connect to database
\c tsunami_db

# Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
```

#### 3. Setup Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 4. Configure Environment

```bash
# Copy .env.example
cp .env.example .env

# Edit .env
nano .env
```

Update konfigurasi:
```env
DATABASE_URL=postgresql://tsunami_user:your_password@localhost:5432/tsunami_db
MODEL_RESNET_PATH=trained_models/pi_resnet50.pth
MODEL_MMVIT_PATH=trained_models/pi_mmvit.pth
```

#### 5. Initialize Database

```bash
# Run migrations (if using Alembic)
alembic upgrade head

# Or initialize directly
python -c "from app.database.connection import init_db; import asyncio; asyncio.run(init_db())"
```

#### 6. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API tersedia di:
- **Base URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📡 API Endpoints

### Health Check
```
GET  /api/health      # Health check dengan metrics
GET  /api/ping        # Simple ping
```

### Simulation (Manual)
```
POST /api/v1/simulation/run              # Jalankan simulasi
GET  /api/v1/simulation/{simulation_id}  # Get simulasi by ID
```

**Request Body Example:**
```json
{
  "magnitude": 7.5,
  "depth": 20.0,
  "latitude": -6.102,
  "longitude": 105.423
}
```

### Real-Time Monitoring
```
GET  /api/v1/earthquakes/realtime          # Fetch gempa terkini
GET  /api/v1/earthquakes/{earthquake_id}   # Get gempa by ID
```

**Query Parameters:**
- `limit`: Jumlah data (default: 10)
- `min_magnitude`: Magnitudo minimum (default: 5.0)
- `hours`: Rentang waktu dalam jam (default: 24)

### History
```
GET    /api/v1/simulation/history  # Riwayat simulasi
DELETE /api/v1/simulation/history/{id}  # Hapus simulasi
GET    /api/v1/earthquakes/history  # Riwayat gempa
```

## 🧪 Testing

### Run Tests
```bash
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test
pytest tests/test_api.py::test_simulation_endpoint
```

### API Testing dengan Postman

1. Import collection dari `tests/postman_collection.json`
2. Set environment variable `base_url` = `http://localhost:8000`
3. Run collection tests

### Manual Testing

```bash
# Test simulation endpoint
curl -X POST "http://localhost:8000/api/v1/simulation/run" \
  -H "Content-Type: application/json" \
  -d '{
    "magnitude": 7.5,
    "depth": 20.0,
    "latitude": -6.102,
    "longitude": 105.423
  }'

# Test realtime earthquakes
curl "http://localhost:8000/api/v1/earthquakes/realtime?limit=5&min_magnitude=5.0"
```

## 📦 Deployment

### Deploy ke Render

1. Push code ke GitHub
2. Buat akun di [Render](https://render.com)
3. Create New Web Service
4. Connect repository
5. Set environment variables
6. Deploy

### Deploy ke Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up
```

### Environment Variables untuk Production

```env
DEBUG=False
DATABASE_URL=postgresql://user:password@host:5432/db
ALLOWED_ORIGINS=["https://your-frontend.vercel.app"]
ENABLE_REALTIME_MONITORING=True
MODEL_RESNET_PATH=trained_models/pi_resnet50.pth
MODEL_MMVIT_PATH=trained_models/pi_mmvit.pth
USE_GPU=False
```

## 📊 Database Schema

### Simulations Table
```sql
CREATE TABLE simulations (
    id UUID PRIMARY KEY,
    magnitude FLOAT NOT NULL,
    depth FLOAT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    epicenter GEOMETRY(Point, 4326),
    prediction_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    processing_time_ms INTEGER
);
```

### Earthquakes Table
```sql
CREATE TABLE earthquakes (
    id VARCHAR(100) PRIMARY KEY,
    magnitude FLOAT NOT NULL,
    depth FLOAT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    location GEOMETRY(Point, 4326),
    location_name TEXT,
    timestamp TIMESTAMP NOT NULL,
    source VARCHAR(50) NOT NULL,
    tsunami_potential BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🔧 Troubleshooting

### Import Error: No module named 'app'
```bash
# Pastikan PYTHONPATH sudah diset
export PYTHONPATH=$PWD
```

### Database Connection Error
```bash
# Test koneksi PostgreSQL
psql -h localhost -U tsunami_user -d tsunami_db

# Check PostGIS extension
SELECT PostGIS_version();
```

### GDAL/Rasterio Installation Error
```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin libgdal-dev

# macOS
brew install gdal

# Reinstall rasterio
pip install rasterio --no-binary rasterio
```

## 📝 Dokumentasi Lengkap

- **API Documentation**: http://localhost:8000/docs
- **Frontend Repository**: https://github.com/Fatehhh23/Frontend-Skripsi-2
- **Proposal Skripsi**: [Link ke proposal]

## 💬 Kontribusi

Untuk kontribusi atau bug report, silakan buat issue di GitHub.

## 📝 Lisensi

Proyek ini adalah bagian dari Tugas Akhir/Skripsi dan tidak untuk dipublikasikan secara komersial.

## 👨‍💻 Author

**Muhamad Fatih Rizqi**  
Jurusan Teknik Elektro  
Fakultas Teknik  
Universitas Lampung  
2026

---

**AVATAR** - Advanced Visualization & Analysis for Tsunami Alert Response
