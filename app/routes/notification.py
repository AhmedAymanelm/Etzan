"""
Notification routes for regular users.
Handles device token registration/unregistration for push notifications.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.device_token import UserDeviceToken

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ─── Schemas ───────────────────────────────────────────────────────────────────

class RegisterDeviceRequest(BaseModel):
    fcm_token: str
    device_type: Optional[str] = None   # "android" | "ios"
    device_name: Optional[str] = None   # e.g. "iPhone 15 Pro"


class UnregisterDeviceRequest(BaseModel):
    fcm_token: str


# ─── Register Device Token ────────────────────────────────────────────────────

@router.post("/register-device", summary="Register an FCM device token")
async def register_device(
    body: RegisterDeviceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new FCM device token for push notifications.
    If the token already exists for this user, it will be updated.
    If the token exists for a different user, it will be reassigned.
    """
    token = body.fcm_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="FCM token cannot be empty")

    # Check if token already exists
    result = await db.execute(
        select(UserDeviceToken).where(UserDeviceToken.fcm_token == token)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Token exists — update ownership and reactivate
        existing.user_id = current_user.id
        existing.device_type = body.device_type or existing.device_type
        existing.device_name = body.device_name or existing.device_name
        existing.is_active = True
        await db.commit()
        return {"message": "تم تحديث رمز الجهاز بنجاح", "status": "updated"}

    # Create new token
    device_token = UserDeviceToken(
        user_id=current_user.id,
        fcm_token=token,
        device_type=body.device_type,
        device_name=body.device_name,
        is_active=True,
    )
    db.add(device_token)
    await db.commit()

    return {"message": "تم تسجيل الجهاز بنجاح", "status": "registered"}


# ─── Unregister Device Token ──────────────────────────────────────────────────

@router.post("/unregister-device", summary="Unregister an FCM device token")
async def unregister_device(
    body: UnregisterDeviceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unregister a device token (e.g. on logout).
    Marks the token as inactive rather than deleting it.
    """
    token = body.fcm_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="FCM token cannot be empty")

    result = await db.execute(
        select(UserDeviceToken).where(
            UserDeviceToken.fcm_token == token,
            UserDeviceToken.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.is_active = False
        await db.commit()
        return {"message": "تم إلغاء تسجيل الجهاز", "status": "unregistered"}

    return {"message": "رمز الجهاز غير موجود", "status": "not_found"}
