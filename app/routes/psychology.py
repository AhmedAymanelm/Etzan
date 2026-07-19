from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user, get_optional_current_user
from app.models.history import AssessmentHistory

from ..models.psychology import QuestionnaireResponse, AnswersSubmission, AssessmentResult
from ..services.psychology_service import PsychologyService


router = APIRouter(prefix="/psychology", tags=["psychology"])


@router.get("", response_model=QuestionnaireResponse)
async def get_psychology_questionnaire(db: AsyncSession = Depends(get_db)):
    """
    Get psychology assessment questionnaire
    
    Returns:
        QuestionnaireResponse: Complete questionnaire with all questions
    """
    return await PsychologyService.get_questionnaire_from_db(db)


@router.post("/submit", response_model=AssessmentResult)
async def submit_psychology_answers(
    submission: AnswersSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Submit user answers and calculate result
    
    Args:
        submission: User answers (7 answers, each between 1 and 3)
    
    Returns:
        AssessmentResult: Final result with level and message
    
    Raises:
        HTTPException: If validation fails
    """
    try:
        result = PsychologyService.calculate_assessment(submission.answers)
        
        # Save to history
        if current_user:
            history_entry = AssessmentHistory(
                user_id=current_user.id,
                assessment_type="psychology",
                input_data={"answers": submission.answers},
                result_data=result.model_dump()
            )
            db.add(history_entry)
            await db.commit()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
