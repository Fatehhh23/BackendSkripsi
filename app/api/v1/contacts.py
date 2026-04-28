from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.database.connection import get_db
from app.database.models import ContactMessage, User
from app.schemas.contact import (
    ContactMessageCreate,
    ContactMessageResponse,
    ContactMessageUpdate
)
from app.core.dependencies import get_current_admin_user

router = APIRouter()

@router.post("", response_model=ContactMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_contact_message(
    message: ContactMessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Kirim pesan baru dari form kontak (Public).
    """
    new_message = ContactMessage(
        name=message.name,
        email=message.email,
        subject=message.subject,
        message=message.message,
        status="unread"
    )
    
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    return new_message

@router.get("/admin", response_model=list[ContactMessageResponse])
async def get_all_contact_messages(
    status_filter: Optional[str] = Query(None, description="Filter by status ('unread' or 'resolved')"),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Ambil semua pesan kontak (Khusus Admin).
    Bisa difilter berdasarkan status (unread/resolved).
    """
    query = select(ContactMessage).order_by(desc(ContactMessage.created_at))
    
    if status_filter:
        if status_filter not in ["unread", "resolved"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter. Must be 'unread' or 'resolved'"
            )
        query = query.where(ContactMessage.status == status_filter)
        
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return messages

@router.put("/admin/{message_id}/status", response_model=ContactMessageResponse)
async def update_message_status(
    message_id: UUID,
    update_data: ContactMessageUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Ubah status pesan kontak (Khusus Admin).
    Misal dari 'unread' menjadi 'resolved'.
    """
    if update_data.status not in ["unread", "resolved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be 'unread' or 'resolved'"
        )
        
    result = await db.execute(select(ContactMessage).where(ContactMessage.id == message_id))
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
        
    message.status = update_data.status
    await db.commit()
    await db.refresh(message)
    
    return message


@router.delete("/admin/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Hapus pesan kontak (Khusus Admin).
    """
    result = await db.execute(select(ContactMessage).where(ContactMessage.id == message_id))
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
        
    await db.delete(message)
    await db.commit()
    return None
