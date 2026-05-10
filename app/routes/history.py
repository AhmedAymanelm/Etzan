from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.history import AssessmentHistory

router = APIRouter(prefix="/history", tags=["history"])

@router.get("", response_model=Dict[str, Any])
async def get_assessment_history(
    assessment_type: Optional[str] = Query(None, description="Filter by type (psychology, neuroscience, letter, astrology, comprehensive)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the assessment history for the currently logged-in user.
    """
    query = select(AssessmentHistory).where(AssessmentHistory.user_id == current_user.id)
    
    if assessment_type:
        query = query.where(AssessmentHistory.assessment_type == assessment_type)
        
    query = query.order_by(desc(AssessmentHistory.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    history_records = result.scalars().all()
    
    # Format the response
    formatted_records = []
    for record in history_records:
        formatted_records.append({
            "id": str(record.id),
            "type": record.assessment_type,
            "created_at": record.created_at.isoformat(),
            "input_data": record.input_data,
            "result_data": record.result_data,
        })
        
    return {
        "count": len(formatted_records),
        "limit": limit,
        "offset": offset,
        "results": formatted_records
    }
