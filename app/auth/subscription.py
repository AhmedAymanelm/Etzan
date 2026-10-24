"""
Subscription access control dependency.

Usage: add `_: bool = Depends(check_subscription_access)` to any
analysis endpoint you want to protect.

Logic:
  0. Payment gateway is INACTIVE → allow immediately (bypass payment)
  1. Active (non-expired) UserSubscription → allow
  2. No subscription but free_trial_used == False → allow + mark trial as used
  3. No subscription + free_trial_used == True → raise 402
"""

from datetime import datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.subscription import UserSubscription


async def _is_gateway_active(db: AsyncSession) -> bool:
    """Returns True if the Fawaterk payment gateway is set to active in settings."""
    from app.models.settings import SystemSetting
    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.key == "fawaterk_status"
        )
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        return True  # default: treat as active if not configured
    return setting.value.lower() == "active"


async def check_subscription_access(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """
    Gate that allows access to analysis endpoints only if:
    - Payment gateway is INACTIVE (bypass all payment checks), OR
    - The user has an active (non-expired) monthly subscription, OR
    - The user has not yet used their one free trial.

    Raises HTTP 402 with a structured JSON body when access is denied.
    Returns True when access is granted.
    """

    # ── 0. Check gateway status — if inactive, bypass everything ─────────────
    gateway_active = await _is_gateway_active(db)
    if not gateway_active:
        return True  # Gateway off → free access for everyone

    # ── 1. Check for an active, non-expired subscription ─────────────────────
    result = await db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.is_active == True,
            UserSubscription.expires_at > datetime.utcnow(),
        )
    )
    active_sub = result.scalar_one_or_none()

    if active_sub:
        return True  

    # ── 2. No active subscription — check free trial ──────────────────────────
    if not current_user.free_trial_used:
        # Mark trial as consumed (atomic with the rest of the request transaction)
        current_user.free_trial_used = True
        db.add(current_user)
        await db.commit()
        return True  

    # ── 3. Trial already used and no subscription → block ────────────────────
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "SUBSCRIPTION_REQUIRED",
            "message": "لقد استُهلكت تجربتك المجانية. يرجى الاشتراك الشهري للمتابعة.",
            "message_en": "Your free trial has been used. Please subscribe to continue.",
            "service_type": "monthly_subscription",
        },
    )
