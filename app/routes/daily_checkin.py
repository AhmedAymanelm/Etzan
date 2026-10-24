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


@router.get("/stats", summary="Get user's personal check-in statistics")
async def get_user_checkin_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns personal weekly check-in stats for the current user:
    - total_days: how many days they've submitted
    - streak: current consecutive day streak
    - weekly_counts: last 7 days submission count (0 or 1 per day)
    - last_7_answers: last 7 responses with answers for mood trend
    - completion_rate: percentage of days completed out of last 30 days
    """
    from datetime import date, timedelta

    today = date.today()
    user_id_str = str(current_user.id)

    # All user responses (last 30 days)
    thirty_days_ago = today - timedelta(days=29)
    result = await db.execute(
        select(DailyCheckInResponse)
        .where(
            and_(
                DailyCheckInResponse.user_id == user_id_str,
                DailyCheckInResponse.date >= thirty_days_ago
            )
        )
        .order_by(DailyCheckInResponse.date.desc())
    )
    responses = result.scalars().all()

    # Total days submitted
    total_days = len(responses)

    # Completion rate (last 30 days)
    completion_rate = round((total_days / 30) * 100, 1)

    # Current streak
    streak = 0
    check_date = today
    submitted_dates = {r.date for r in responses}
    while check_date in submitted_dates:
        streak += 1
        check_date -= timedelta(days=1)

    # Last 7 days: did user submit? (1 or 0 per day)
    weekly_counts = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_name_map = {
            0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء",
            3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"
        }
        weekly_counts.append({
            "date": str(day),
            "day_name": day_name_map[day.weekday()],
            "submitted": day in submitted_dates,
            "is_today": day == today
        })

    # Last 7 responses with answers for mood analysis
    last_7 = [r.to_dict() for r in responses[:7]]

    # Get active questions for context
    q_result = await db.execute(
        select(DailyCheckInQuestion)
        .where(DailyCheckInQuestion.is_active == True)
        .order_by(DailyCheckInQuestion.order_index)
    )
    questions = q_result.scalars().all()

    return {
        "total_days": total_days,
        "streak": streak,
        "completion_rate": completion_rate,
        "weekly_counts": weekly_counts,
        "last_7_responses": last_7,
        "questions": [q.to_dict() for q in questions],
    }
