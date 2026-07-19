from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user, get_optional_current_user
from app.models.history import AssessmentHistory
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator
from ..models.astrology import AstrologyRequest, AstrologyResponse, BirthDataInput
from ..services.astrology_service import AstrologyService

import asyncio
import json

router = APIRouter(prefix="/astrology", tags=["astrology"])


@router.post("/analyze", response_model=AstrologyResponse)
async def analyze_daily_horoscope(
    request: AstrologyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    تحليل البرج اليومي وإرجاع التحليل النفسي الشامل
    """
    try:
        result = await AstrologyService.analyze(request)
        
        # Save to history
        if current_user:
            history_entry = AssessmentHistory(
                user_id=current_user.id,
                assessment_type="astrology",
                input_data=request.model_dump(),
                result_data=result.model_dump()
            )
            db.add(history_entry)
            await db.commit()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

