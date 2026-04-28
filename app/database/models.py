from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, Text, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
# from geoalchemy2 import Geometry  # TEMP: Commented out - requires GDAL/PROJ libraries
from datetime import datetime
import uuid
import enum

from app.database.connection import Base

# ============================================
# Enums
# ============================================

class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

# ============================================
# Models
# ============================================

class User(Base):
    """Model untuk user authentication dan management"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Credentials
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # Hashed password
    
    # Profile
    full_name = Column(String(255), nullable=True)
    
    # Role & Status
    # Use values_callable to ensure enum VALUE (not NAME) is used in database
    role = Column(
        SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    simulations = relationship("Simulation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username} - {self.role.value}>"


class Simulation(Base):
    """Model untuk menyimpan riwayat simulasi"""
    __tablename__ = "simulations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Input parameters
    magnitude = Column(Float, nullable=False)
    depth = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    mode = Column(String(20), default="AI", nullable=False) # AI or HEURISTIC
    
    # Epicenter as PostGIS Point
    # TEMP: Commented out - requires geoalchemy2
    # epicenter = Column(Geometry('POINT', srid=4326), nullable=True)
    
    # Prediction results (stored as JSON)
    prediction_data = Column(JSON, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_session_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Processing metrics
    processing_time_ms = Column(Integer, nullable=True)
    model_version = Column(String(50), nullable=True)
    
    # Relationship
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="simulations")
    
    def __repr__(self):
        return f"<Simulation {self.id}: M{self.magnitude} at ({self.latitude}, {self.longitude})>"

class Earthquake(Base):
    """Model untuk menyimpan data gempa real-time"""
    __tablename__ = "earthquakes"
    
    id = Column(String(100), primary_key=True)  # ID from BMKG/USGS
    
    # Earthquake parameters
    magnitude = Column(Float, nullable=False)
    depth = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Location as PostGIS Point
    # TEMP: Commented out - requires geoalchemy2
    # location = Column(Geometry('POINT', srid=4326), nullable=True)
    
    # Metadata
    location_name = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(50), nullable=False)  # BMKG or USGS
    
    # Tsunami assessment (if analyzed)
    tsunami_potential = Column(Boolean, default=False)
    tsunami_risk_level = Column(String(50), nullable=True)  # Rendah, Sedang, Bahaya
    max_wave_height = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Earthquake {self.id}: M{self.magnitude} at {self.timestamp}>"

class InundationZone(Base):
    """Model untuk menyimpan zona genangan tsunami"""
    __tablename__ = "inundation_zones"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id = Column(UUID(as_uuid=True), nullable=False)  # Foreign key to Simulation
    
    # Geometry as PostGIS Polygon
    # TEMP: Commented out - requires geoalchemy2
    # geometry = Column(Geometry('POLYGON', srid=4326), nullable=False)
    
    # Wave characteristics
    wave_height = Column(Float, nullable=False)  # meter
    arrival_time = Column(Integer, nullable=False)  # minutes
    
    # Area statistics
    area_sqkm = Column(Float, nullable=True)
    affected_population = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<InundationZone {self.id}: {self.wave_height}m>"

class CoastlineData(Base):
    """Model untuk data garis pantai (reference data)"""
    __tablename__ = "coastlines"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    
    # Coastline as PostGIS LineString
    # TEMP: Commented out - requires geoalchemy2
    # geometry = Column(Geometry('LINESTRING', srid=4326), nullable=False)
    
    # Metadata
    region = Column(String(100), nullable=True)
    length_km = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Coastline {self.name}>"

class ContactMessage(Base):
    """Model untuk menyimpan pesan dari form kontak user"""
    __tablename__ = "contact_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="unread", nullable=False) # 'unread' or 'resolved'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ContactMessage {self.id} from {self.name} - {self.status}>"
