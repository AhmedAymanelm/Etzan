import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.about import AboutSection
from app.schemas.about import AboutSectionCreate, AboutSectionUpdate, AboutSectionResponse

router = APIRouter(prefix="/about", tags=["About Content"])
admin_router = APIRouter(prefix="/admin/about", tags=["Admin About Content"])

async def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

# ─── Public Endpoints ───

@router.get("", response_model=List[AboutSectionResponse], summary="Get about sections")
async def get_about_sections(
    limit: int = Query(100, description="Number of items to return"),
    offset: int = Query(0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint to get about sections for the Flutter app.
    Returns all items by default.
    """
    result = await db.execute(
        select(AboutSection)
        .order_by(AboutSection.order.asc(), AboutSection.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()

# ─── Admin Endpoints ───

@admin_router.get("", response_model=List[AboutSectionResponse], summary="Get all about sections for admin")
async def get_all_about_sections_admin(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Admin endpoint to fetch all items at once for the dashboard"""
    result = await db.execute(select(AboutSection).order_by(AboutSection.order.asc(), AboutSection.created_at.asc()))
    return result.scalars().all()

@admin_router.post("", response_model=AboutSectionResponse, status_code=status.HTTP_201_CREATED, summary="Add a new about section")
async def create_about_section(
    section: AboutSectionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    new_section = AboutSection(
        title=section.title,
        content=section.content,
        order=section.order
    )
    db.add(new_section)
    await db.commit()
    await db.refresh(new_section)
    return new_section

@admin_router.put("/{section_id}", response_model=AboutSectionResponse, summary="Update an about section")
async def update_about_section(
    section_id: uuid.UUID,
    section_update: AboutSectionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(AboutSection).where(AboutSection.id == section_id))
    db_section = result.scalars().first()
    
    if not db_section:
        raise HTTPException(status_code=404, detail="Section not found")
        
    update_data = section_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_section, key, value)
        
    await db.commit()
    await db.refresh(db_section)
    return db_section

@admin_router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an about section")
async def delete_about_section(
    section_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(AboutSection).where(AboutSection.id == section_id))
    db_section = result.scalars().first()
    
    if not db_section:
        raise HTTPException(status_code=404, detail="Section not found")
        
    await db.delete(db_section)
    await db.commit()
    return None
