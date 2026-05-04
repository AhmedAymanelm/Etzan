from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.profile import ProfileResponse, ProfilePictureUpdateRequest, BirthDetailsUpdateRequest, NameUpdateRequest

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

@router.put("/picture", response_model=ProfileResponse)
async def update_profile_picture(
    request: ProfilePictureUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    تحديث صورة الملف الشخصي للمستخدم
    """
    current_user.profile_picture_url = request.profile_picture_url
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

@router.put("/name", response_model=ProfileResponse)
async def update_fullname(
    request: NameUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    تحديث الاسم الكامل للمستخدم
    """
    current_user.fullname = request.fullname
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

@router.put("/birth-details", response_model=ProfileResponse)
async def update_birth_details(
    request: BirthDetailsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    تحديث بيانات الميلاد للمستخدم (مهمة لاختبار الفلك)
    """
    current_user.date_of_birth = request.date_of_birth
    current_user.city_of_birth = request.city_of_birth
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
