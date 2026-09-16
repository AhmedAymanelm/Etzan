import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.team_member import TeamMember
from app.schemas.team import TeamMemberResponse, TeamMemberUpdate
from app.utils.cloudinary_upload import upload_image_to_cloudinary

router = APIRouter(prefix="/team", tags=["Team"])
admin_router = APIRouter(prefix="/admin/team", tags=["Admin Team"])


async def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# ─── Public Endpoints ───

@router.get("", response_model=List[TeamMemberResponse], summary="Get all team members")
async def get_team_members(db: AsyncSession = Depends(get_db)):
    """Public endpoint to get team members for the Flutter app."""
    result = await db.execute(select(TeamMember).order_by(TeamMember.order.asc(), TeamMember.created_at.asc()))
    members = result.scalars().all()
    return members


# ─── Admin Endpoints ───

@admin_router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED, summary="Add a new team member")
async def create_team_member(
    name: str = Form(...),
    role: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    order: Optional[int] = Form(0),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    image_url = None
    if image and image.filename:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Must be an image.")
        image_url = await upload_image_to_cloudinary(image)

    new_member = TeamMember(
        name=name,
        role=role,
        description=description,
        order=order,
        image_url=image_url
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)
    return new_member


@admin_router.put("/{member_id}", response_model=TeamMemberResponse, summary="Update a team member")
async def update_team_member(
    member_id: uuid.UUID,
    name: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    order: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(TeamMember).where(TeamMember.id == member_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    if name is not None:
        member.name = name
    if role is not None:
        member.role = role
    if description is not None:
        member.description = description
    if order is not None:
        member.order = order

    if image and image.filename:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Must be an image.")
        member.image_url = await upload_image_to_cloudinary(image)

    await db.commit()
    await db.refresh(member)
    return member


@admin_router.delete("/{member_id}", summary="Delete a team member")
async def delete_team_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(TeamMember).where(TeamMember.id == member_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    await db.delete(member)
    await db.commit()
    return {"message": "Team member deleted successfully"}
