from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from app.database.connection import get_db
from app.database.models import User, Simulation, UserRole
from app.database import crud
from app.schemas.admin import (
    UserListResponse, 
    UserListItem,
    UpdateRoleRequest,
    UpdateStatusRequest,
    SystemStats,
    SimulationListResponse,
    SimulationListItem
)
from app.core.dependencies import get_current_admin_user

router = APIRouter()

# ============================================
# User Management Endpoints
# ============================================

@router.get("/users", response_model=UserListResponse)
async def get_all_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get all users with pagination and filtering.
    
    **Admin only** - Requires admin role.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **search**: Search by email or username
    - **role_filter**: Filter by role (user/admin)
    
    Returns paginated list of users.
    """
    
    # Build query with simulation count
    query = (
        select(User, func.count(Simulation.id).label("total_simulations"))
        .outerjoin(Simulation, User.simulations)
        .group_by(User.id)
    )
    
    # Apply filters
    filters = []
    if search:
        search_pattern = f"%{search}%"
        filters.append(
            (User.email.ilike(search_pattern)) | 
            (User.username.ilike(search_pattern))
        )
    
    if role_filter:
        if role_filter == "admin":
            filters.append(User.role == UserRole.ADMIN)
        elif role_filter == "user":
            filters.append(User.role == UserRole.USER)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(User)
    if filters:
        count_query = count_query.where(and_(*filters))
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Map to response
    user_list = []
    for user, sim_count in rows:
        user_data = UserListItem.model_validate(user)
        user_data.total_simulations = sim_count
        user_list.append(user_data)
    
    return UserListResponse(
        users=user_list,
        total=total,
        page=page,
        page_size=page_size
    )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Delete a user account.
    
    **Admin only** - Requires admin role.
    
    - **user_id**: UUID of user to delete
    
    Note: Cannot delete yourself!
    """
    
    # Prevent self-deletion
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Find user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete user
    await db.delete(user)
    await db.commit()
    
    return None

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    request: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Update user role.
    
    **Admin only** - Requires admin role.
    
    - **user_id**: UUID of user to update
    - **role**: New role ('user' or 'admin')
    
    Note: Cannot change your own role!
    """
    
    # Validate role
    if request.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'user' or 'admin'"
        )
    
    # Prevent self-role change
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    # Find user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update role
    user.role = UserRole.ADMIN if request.role == "admin" else UserRole.USER
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "User role updated successfully",
        "user": UserListItem.model_validate(user)
    }

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    request: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Activate or deactivate user account.
    
    **Admin only** - Requires admin role.
    
    - **user_id**: UUID of user to update
    - **is_active**: True to activate, False to deactivate
    
    Note: Cannot deactivate yourself!
    """
    
    # Prevent self-deactivation
    if user_id == current_admin.id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Find user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update status
    user.is_active = request.is_active
    await db.commit()
    await db.refresh(user)
    
    status_text = "activated" if request.is_active else "deactivated"
    
    return {
        "message": f"User {status_text} successfully",
        "user": UserListItem.model_validate(user)
    }

# ============================================
# Analytics Endpoints
# ============================================

@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get system statistics.
    
    **Admin only** - Requires admin role.
    
    Returns:
    - Total users
    - Active users
    - Admin users
    - Total simulations
    - Recent registrations (last 24h)
    - Recent simulations (last 24h)
    """
    
    # Get user stats
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_users = await db.scalar(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    admin_users = await db.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    
    # Get simulation stats
    total_simulations = await db.scalar(select(func.count()).select_from(Simulation))
    
    # Get recent stats (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    recent_registrations = await db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= yesterday)
    )
    
    recent_simulations = await db.scalar(
        select(func.count()).select_from(Simulation).where(Simulation.created_at >= yesterday)
    )
    
    return SystemStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        admin_users=admin_users or 0,
        total_simulations=total_simulations or 0,
        recent_registrations_24h=recent_registrations or 0,
        recent_simulations_24h=recent_simulations or 0
    )

@router.get("/simulations", response_model=SimulationListResponse)
async def get_all_simulations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get all simulations from all users.
    
    **Admin only** - Requires admin role.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    
    Returns paginated list of simulations.
    """
    
    # Get total count
    total = await db.scalar(select(func.count()).select_from(Simulation))
    
    # Build query with pagination
    offset = (page - 1) * page_size
    query = select(Simulation).offset(offset).limit(page_size).order_by(Simulation.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    simulations = result.scalars().all()
    
    return SimulationListResponse(
        simulations=[SimulationListItem.model_validate(sim) for sim in simulations],
        total=total or 0,
        page=page,
        page_size=page_size
    )

@router.delete("/users/{user_id}/simulations", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_history(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Delete all simulation history for a specific user.
    
    **Admin only** - Requires admin role.
    """
    
    # Check if user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete history
    await crud.delete_user_simulation_history(db, user_id)
    
    return None
