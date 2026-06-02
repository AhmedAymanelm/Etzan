from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.models.history import AssessmentHistory

from ..models.neuroscience import (
    NeuroscienceQuestionnaireResponse,
    NeuroscienceAnswersSubmission,
    NeuroscienceAssessmentResult
)
from ..services.neuroscience_service import NeuroscienceService

router = APIRouter(prefix="/neuroscience", tags=["neuroscience"])


@router.get("/questions", response_model=NeuroscienceQuestionnaireResponse)
async def get_neuroscience_questionnaire(db: AsyncSession = Depends(get_db)):
    """
    Get neuroscience assessment questionnaire
    
    Returns:
        NeuroscienceQuestionnaireResponse: Complete questionnaire with questions
    """
    return await NeuroscienceService.get_questionnaire_from_db(db)


from app.utils.settings_helper import get_env_or_db, get_random_setting_item

@router.post("/submit", response_model=NeuroscienceAssessmentResult)
async def submit_neuroscience_answers(
    submission: NeuroscienceAnswersSubmission,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit user answers and calculate neural pattern
    
    Args:
        submission: User answers (9 answers, each A, B, C, or D)
    
    Returns:
        NeuroscienceAssessmentResult: Result with dominant and secondary patterns
    
    Raises:
        HTTPException 422: If validation fails
    """
    try:
        result = NeuroscienceService.calculate_assessment(submission.answers)
        
        # Determine base pattern from dominant
        base_pattern = result.dominant.replace("Mixed ", "").split("/")[0].strip()
        music_url = await get_random_setting_item(f"neuro_music_{base_pattern.lower()}")
        
        if music_url:
            result.background_music_url = music_url
        
        # Save to history
        history_entry = AssessmentHistory(
            user_id=current_user.id,
            assessment_type="neuroscience",
            input_data={"answers": submission.answers},
            result_data=result.model_dump()
        )
        db.add(history_entry)
        await db.commit()
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
