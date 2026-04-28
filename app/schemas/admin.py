from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

# ============================================
# Request Schemas
# ============================================

class UpdateRoleRequest(BaseModel):
    """Request to update user role"""
    role: str  # 'user' or 'admin'

class UpdateStatusRequest(BaseModel):
    """Request to activate/deactivate user"""
    is_active: bool

# ============================================
# Response Schemas
# ============================================

class UserListItem(BaseModel):
    """User item in list"""
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_simulations: int = 0
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    """Paginated list of users"""
    users: List[UserListItem]
    total: int
    page: int
    page_size: int

class SystemStats(BaseModel):
    """System statistics for admin dashboard"""
    total_users: int
    active_users: int
    admin_users: int
    total_simulations: int
    recent_registrations_24h: int
    recent_simulations_24h: int

class SimulationListItem(BaseModel):
    """Simulation item for admin view"""
    id: UUID
    magnitude: float
    depth: float
    latitude: float
    longitude: float
    created_at: datetime
    user_session_id: Optional[str]
    processing_time_ms: Optional[int]
    
    class Config:
        from_attributes = True

class SimulationListResponse(BaseModel):
    """Paginated list of simulations"""
    simulations: List[SimulationListItem]
    total: int
    page: int
    page_size: int
