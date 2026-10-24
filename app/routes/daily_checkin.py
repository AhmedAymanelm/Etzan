from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.daily_checkin import DailyCheckInQuestion, DailyCheckInResponse

router = APIRouter(prefix="/daily-checkin", tags=["Daily Check-In"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SubmitCheckInRequest(BaseModel):
    answers: dict  # {question_id (str): selected_option_index (int)}


# ─── User Endpoints ───────────────────────────────────────────────────────────

@router.get("/questions", summary="Get active daily check-in questions")
async def get_checkin_questions(db: AsyncSession = Depends(get_db)):
    """Returns all active daily check-in questions ordered by order_index."""
    result = await db.execute(
        select(DailyCheckInQuestion)
        .where(DailyCheckInQuestion.is_active == True)
        .order_by(DailyCheckInQuestion.order_index)
    )
    questions = result.scalars().all()
    return [q.to_dict() for q in questions]


@router.post("/submit", summary="Submit daily check-in answers")
async def submit_checkin(
    data: SubmitCheckInRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit today's daily check-in. Only one submission per day per user."""
    today = date.today()
    user_id_str = str(current_user.id)

    # Check if already submitted today
    existing = await db.execute(
        select(DailyCheckInResponse).where(
            and_(
                DailyCheckInResponse.user_id == user_id_str,
                DailyCheckInResponse.date == today
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لقد قمت بالتسجيل اليومي بالفعل"
        )

    response = DailyCheckInResponse(
        user_id=user_id_str,
        date=today,
        answers=data.answers
    )
    db.add(response)
    await db.commit()

    return {"message": "تم حفظ التسجيل اليومي بنجاح", "date": today.isoformat()}


@router.get("/today", summary="Check if user already submitted today")
async def get_today_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns today's submission if it exists."""
    today = date.today()
    user_id_str = str(current_user.id)

    result = await db.execute(
        select(DailyCheckInResponse).where(
            and_(
                DailyCheckInResponse.user_id == user_id_str,
                DailyCheckInResponse.date == today
            )
        )
    )
    response = result.scalar_one_or_none()
    if response:
        return {"submitted": True, "data": response.to_dict()}
    return {"submitted": False, "data": None}


@router.get("/history", summary="Get user's check-in history")
async def get_checkin_history(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns the last N daily check-in submissions for the current user."""
    user_id_str = str(current_user.id)
    result = await db.execute(
        select(DailyCheckInResponse)
        .where(DailyCheckInResponse.user_id == user_id_str)
        .order_by(DailyCheckInResponse.date.desc())
        .limit(limit)
    )
    responses = result.scalars().all()
    return [r.to_dict() for r in responses]
