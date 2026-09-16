from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import datetime
from typing import List, Dict

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.history import AssessmentHistory
from app.models.goal import DailyGoal as DailyGoalModel
from app.schemas.statistics import UserStatisticsResponse, DailyMood, DailyGoal as DailyGoalSchema

router = APIRouter(prefix="/statistics", tags=["statistics"])

ARABIC_DAYS = {
    0: "إثنين",
    1: "ثلاثاء",
    2: "أربعاء",
    3: "خميس",
    4: "جمعة",
    5: "سبت",
    6: "أحد"
}

@router.get("/user", response_model=UserStatisticsResponse, summary="Get user statistics based on history")
async def get_user_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get the date 7 days ago
    today = datetime.datetime.utcnow().date()
    seven_days_ago = today - datetime.timedelta(days=6)
    
    # Query assessment history for the last 7 days
    result = await db.execute(
        select(AssessmentHistory)
        .where(
            AssessmentHistory.user_id == current_user.id,
            AssessmentHistory.created_at >= datetime.datetime.combine(seven_days_ago, datetime.time.min)
        )
    )
    histories = result.scalars().all()
    
    # Initialize the last 7 days data
    days_data: Dict[str, dict] = {}
    for i in range(7):
        date_obj = today - datetime.timedelta(days=6 - i)
        day_str = ARABIC_DAYS[date_obj.weekday()]
        date_key = date_obj.isoformat()
        days_data[date_key] = {
            "day": day_str,
            "completed": 0,
            "mood_value": 0, # Default: 0 = لم يسجل
            "mood_str": "لم يسجل",
            "psychology_scores": []
        }
        
    all_scores = []

    # Query daily goals for the last 7 days
    goals_result = await db.execute(
        select(DailyGoalModel)
        .where(
            DailyGoalModel.user_id == current_user.id,
            DailyGoalModel.target_date >= seven_days_ago
        )
    )
    goals_records = goals_result.scalars().all()
    
    # Process history records (for mood calculations)
    for record in histories:
        date_key = record.created_at.date().isoformat()
        if date_key in days_data:
            # Extract mood/score from psychology assessments
            if record.assessment_type == "psychology":
                score = record.result_data.get("score", 0)
                if score > 0:
                    days_data[date_key]["psychology_scores"].append(score)
                    all_scores.append(score)

    # Process goals
    today_key = today.isoformat()
    completed_goals_today = 0
    total_goals_today = 0
    
    for goal in goals_records:
        date_key = goal.target_date.isoformat()
        if date_key in days_data:
            if date_key == today_key:
                total_goals_today += 1
                if goal.is_completed:
                    completed_goals_today += 1
                    
            if goal.is_completed:
                days_data[date_key]["completed"] += 1

    # Calculate Daily Moods and Goals
    daily_moods = []
    weekly_goals = []
    
    for date_key in sorted(days_data.keys()):
        data = days_data[date_key]
        
        # Determine Mood for the day based on average score
        if data["psychology_scores"]:
            avg_score = sum(data["psychology_scores"]) / len(data["psychology_scores"])
            if avg_score <= 12:
                mood_val = 3
                mood_str = "هادئ"
            elif avg_score <= 16:
                mood_val = 2
                mood_str = "متوتر"
            else:
                mood_val = 1
                mood_str = "عصبي"
        else:
            # If no psychology test, check if they did any activity. If yes, default to calm (3) or just keep 0
            if data["completed"] > 0:
                mood_val = 3
                mood_str = "هادئ"
            else:
                mood_val = 0
                mood_str = "لم يسجل"
                
        daily_moods.append(DailyMood(
            day=data["day"],
            mood=mood_str,
            mood_value=mood_val
        ))
        
        weekly_goals.append(DailyGoalSchema(
            day=data["day"],
            completed_tasks=data["completed"]
        ))
        
    # Calculate Balance Percentage
    # Assume psychology score ranges from 7 (perfect = 100%) to 21 (worst = 0%)
    if all_scores:
        avg_overall = sum(all_scores) / len(all_scores)
        # normalize: (21 - score) / (21 - 7) * 100
        balance = int(((21 - avg_overall) / 14) * 100)
        balance = max(0, min(100, balance))
    else:
        # If no tests taken, if they have any activity, give them a baseline of 50%, else 0%
        if sum(d.completed_tasks for d in weekly_goals) > 0:
            balance = 50
        else:
            balance = 0

    daily_achievement_percentage = 0
    if total_goals_today > 0:
        daily_achievement_percentage = int((completed_goals_today / total_goals_today) * 100)

    return UserStatisticsResponse(
        balance_percentage=balance,
        daily_achievement_percentage=daily_achievement_percentage,
        completed_goals_today=completed_goals_today,
        total_goals_today=total_goals_today,
        daily_moods=daily_moods,
        weekly_goals=weekly_goals
    )



