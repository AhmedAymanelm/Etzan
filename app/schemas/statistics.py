from pydantic import BaseModel
from typing import List

class DailyMood(BaseModel):
    day: str
    mood: str
    mood_value: int # 1 = عصبي (Nervous), 2 = متوتر (Stressed), 3 = هادئ (Calm), 0 = لم يسجل (No Data)

class DailyGoal(BaseModel):
    day: str
    completed_tasks: int

class UserStatisticsResponse(BaseModel):
    balance_percentage: int
    daily_achievement_percentage: int
    completed_goals_today: int
    total_goals_today: int
    daily_moods: List[DailyMood]
    weekly_goals: List[DailyGoal]
