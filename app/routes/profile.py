from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.profile import ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
   
    return ProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        fullname=current_user.fullname,
        date_of_birth=current_user.date_of_birth,
        city_of_birth=current_user.city_of_birth,
        time_of_birth=current_user.time_of_birth,
        profile_picture_url=current_user.profile_picture_url
    )


@router.put("/update", response_model=ProfileResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """تحديث الملف الشخصي - الصورة والاسم والتاريخ في endpoint واحد"""

    if request.profile_picture_url is not None:
        current_user.profile_picture_url = request.profile_picture_url

    if request.fullname is not None:
        current_user.fullname = request.fullname

    if request.date_of_birth is not None:
        current_user.date_of_birth = request.date_of_birth

    if request.city_of_birth is not None:
        current_user.city_of_birth = request.city_of_birth

    if request.time_of_birth is not None:
        current_user.time_of_birth = request.time_of_birth

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return ProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        fullname=current_user.fullname,
        date_of_birth=current_user.date_of_birth,
        city_of_birth=current_user.city_of_birth,
        time_of_birth=current_user.time_of_birth,
        profile_picture_url=current_user.profile_picture_url
    )

@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    
    await db.delete(current_user)
    await db.commit()
    return None
