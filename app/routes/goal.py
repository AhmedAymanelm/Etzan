from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.goal import DailyGoal, UserNote
from app.schemas.goal import GoalCreate, GoalUpdate, GoalResponse, NoteCreate, NoteUpdate, NoteResponse

router = APIRouter(prefix="/activity", tags=["Goals & Notes"])

# ── Daily Goals ────────────────────────────────────────────────────────────

@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal: GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    target = goal.target_date or datetime.utcnow().date()
    new_goal = DailyGoal(
        user_id=current_user.id,
        title=goal.title,
        content=goal.content,
        target_date=target
    )
    db.add(new_goal)
    await db.commit()
    await db.refresh(new_goal)
    return new_goal

@router.get("/goals", response_model=List[GoalResponse])
async def get_goals(
    date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get goals. If date (YYYY-MM-DD) is provided, filter by that date. Defaults to today."""
    query = select(DailyGoal).where(DailyGoal.user_id == current_user.id)
    if date:
        try:
            target = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    else:
        target = datetime.utcnow().date()
        
    query = query.where(DailyGoal.target_date == target).order_by(DailyGoal.created_at.asc())
    result = await db.execute(query)
    return result.scalars().all()

@router.put("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: uuid.UUID,
    goal_update: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(DailyGoal).where(DailyGoal.id == goal_id, DailyGoal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    if goal_update.title is not None:
        goal.title = goal_update.title
    if goal_update.content is not None:
        goal.content = goal_update.content
    if goal_update.is_completed is not None:
        goal.is_completed = goal_update.is_completed
        
    await db.commit()
    await db.refresh(goal)
    return goal

@router.patch("/goals/{goal_id}/toggle", response_model=GoalResponse)
async def toggle_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(DailyGoal).where(DailyGoal.id == goal_id, DailyGoal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    goal.is_completed = not goal.is_completed
    await db.commit()
    await db.refresh(goal)
    return goal

@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(DailyGoal).where(DailyGoal.id == goal_id, DailyGoal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    await db.delete(goal)
    await db.commit()
    return None

# ── User Notes ─────────────────────────────────────────────────────────────

@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_note = UserNote(
        user_id=current_user.id,
        content=note.content
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    return new_note

@router.get("/notes", response_model=List[NoteResponse])
async def get_notes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(UserNote).where(UserNote.user_id == current_user.id).order_by(UserNote.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    note_update: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(UserNote).where(UserNote.id == note_id, UserNote.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
        
    note.content = note_update.content
    await db.commit()
    await db.refresh(note)
    return note

@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(UserNote).where(UserNote.id == note_id, UserNote.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
        
    await db.delete(note)
    await db.commit()
    return None
