from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, delete
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.history import AssessmentHistory
from app.models.payment import PaymentRecord
from app.models.settings import SystemSetting

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

# ─── Schemas ───────────────────────────────────────────────────────────────────
class GrantAdminRequest(BaseModel):
    email: EmailStr

class UpdateSettingRequest(BaseModel):
    value: str

class UpdatePricingRequest(BaseModel):
    amount: float
    currency: str = "EGP"

class UpdateGatewayRequest(BaseModel):
    status: Optional[str] = None
    fees: Optional[str] = None
    fees_type: Optional[str] = None
    description: Optional[str] = None
    api_key: Optional[str] = None
    mode: Optional[str] = None

# ─── Admin Guard ───────────────────────────────────────────────────────────────
async def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ─── Overview Stats ────────────────────────────────────────────────────────────

@router.get("/stats", summary="Get dashboard key metrics")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one_or_none() or 0
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar_one_or_none() or 0
    total_assessments = (await db.execute(select(func.count(AssessmentHistory.id)))).scalar_one_or_none() or 0
