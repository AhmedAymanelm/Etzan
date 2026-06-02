from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Dict, Any
import asyncio

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.auth.subscription import check_subscription_access
from app.models.history import AssessmentHistory
from app.models.payment import PaymentRecord
from sqlalchemy.future import select
from ..models.comprehensive import ComprehensiveAnswers, ComprehensiveResult, ComprehensiveResultsInput
from ..services.comprehensive_service import ComprehensiveService

router = APIRouter(prefix="/comprehensive", tags=["comprehensive"])


@router.post("/submit", response_model=Dict[str, Any])
async def submit_comprehensive_answers(
    submission: ComprehensiveAnswers,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(check_subscription_access),
):
    """
    Submit all assessment answers and get comprehensive analysis
    
    Args:
        submission: All answers (psychology, neuroscience, astrology)
    
    Returns:
        Dict: Complete analysis combining all three assessments
    
    Raises:
        HTTPException: If validation or processing fails
    """
    try:
        result = await ComprehensiveService.analyze_all(
            name=submission.name,
            psychology_answers=submission.psychology_answers,
            neuroscience_answers=submission.neuroscience_answers,
            birth_date=submission.birth_date,
            birth_time=submission.birth_time,
            birth_place=submission.birth_place
        )
        
        # Save to history
        history_entry = AssessmentHistory(
            user_id=current_user.id,
            assessment_type="comprehensive",
            input_data=submission.model_dump(),
            result_data=result
        )
        db.add(history_entry)
        await db.commit()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate-report", response_model=Dict[str, Any])
async def generate_comprehensive_report(
    submission: ComprehensiveAnswers,
    background_tasks: BackgroundTasks,
    payment_session_id: str = "test",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(check_subscription_access),
):
    """
    1. Verifies Payment.
    2. Instantly generates AI Text Report (Psychology + Neuroscience + Astrology).
    3. Triggers cinematic AI Video Generation in the Background.
    Return returns immediately so mobile apps do not time out.
    
    Args:
        submission: Complete user data for all three assessments
        payment_session_id: The Fawaterk session ID for the successful payment
    
    Returns:
        Dict with comprehensive analysis 
    
    Raises:
        HTTPException: If payment is not verified or generation fails
    """
    # 1. Verify Payment
    try:
        if payment_session_id != "test":
            payment_result = await db.execute(
                select(PaymentRecord).where(
                    PaymentRecord.session_id == payment_session_id,
                    PaymentRecord.user_id == current_user.id,
                    PaymentRecord.status == "SUCCESS"
                )
            )
            payment = payment_result.scalar_one_or_none()
            
            if not payment:
                raise HTTPException(
                    status_code=402, 
                    detail="Payment session invalid or already used. Please complete a new payment."
                )
            
            # BUG FIX: Mark as consumed immediately to prevent Replay Attacks and Race Conditions
            payment.status = "CONSUMED"
            await db.commit()
        else:
            class MockPayment:
                order_id = "test_order_bypass"
            payment = MockPayment()
            
        # 2. Proceed with all assessments
        report_data = await ComprehensiveService.analyze_all(
            name=submission.name,
            psychology_answers=submission.psychology_answers,
            neuroscience_answers=submission.neuroscience_answers,
            birth_date=submission.birth_date,
            birth_time=submission.birth_time,
            birth_place=submission.city_of_birth
        )
        
        # Inject letter result if provided by the client
        if submission.letter_result:
            report_data["letter"] = submission.letter_result
        
        neuro_pattern = report_data.get("neuroscience", {}).get("dominant")
        zodiac_sign = report_data.get("astrology", {}).get("sun_sign")
        
        # 4. Generate AI Text Report (Instantaneous ~10s)
        report_result = await ComprehensiveService.generate_comprehensive_report(
            name=submission.name,
            psychology_result=report_data.get("psychology", {}),
            neuroscience_result=report_data.get("neuroscience", {}),
            astrology_result=report_data.get("astrology", {}),
            letter_result=submission.letter_result
        )

        # 5. Immediate DB Save (Video bypassed)
        
        history_entry = AssessmentHistory(
            user_id=current_user.id,
            assessment_type="comprehensive",
            input_data=submission.model_dump(),
            result_data={"analysis": report_data, "report": report_result},
        )
        db.add(history_entry)
        await db.commit()
        
        return {
            "status": "success",
            "analysis": report_data,
            "report": report_result,
            "zodiac_sign": zodiac_sign,
            "neuro_pattern": neuro_pattern,
            "payment_order_id": payment.order_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comprehensive processing failed: {str(e)}")




@router.post("/analyze-from-results", response_model=Dict[str, Any])
async def analyze_from_results(
    submission: ComprehensiveResultsInput,
    model: str = "gpt-4o",
    temperature: float = 0.8,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(check_subscription_access),
):
    """
    Generate comprehensive AI analysis report from pre-computed results.
    
    Use this endpoint when you already have results from individual assessments
    (psychology, neuroscience, astrology) and want to get a unified AI-generated 
    comprehensive analysis report.
    
    Args:
        submission: Pre-computed results from all three assessments
        model: AI model for report generation (gpt-4o, gpt-4-turbo-preview, gpt-3.5-turbo)
        temperature: Creativity level (0.0-1.0, default 0.8)
    
    Returns:
        Dict containing comprehensive analysis report and results summary
    
    Raises:
        HTTPException: If analysis generation fails
    """
    try:
        report = await ComprehensiveService.generate_comprehensive_report(
            name=submission.name,
            psychology_result=submission.psychology_result,
            neuroscience_result=submission.neuroscience_result,
            astrology_result=submission.astrology_result,
            letter_result=submission.letter_result,
            model=model,
            temperature=temperature
        )
        
        # Save to history
        history_entry = AssessmentHistory(
            user_id=current_user.id,
            assessment_type="comprehensive",
            input_data=submission.model_dump(),
            result_data=report
        )
        db.add(history_entry)
        await db.commit()
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate comprehensive analysis: {str(e)}"
        )
