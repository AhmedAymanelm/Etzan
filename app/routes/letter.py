from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user, get_optional_current_user
from typing import Optional
from app.models.history import AssessmentHistory
from app.models.letter_guidance import LetterGuidance

from ..models.letter import (
    LetterAnalysisRequest, 
    LetterAnalysisResponse, 
    GuidanceDictionary,
    LetterGuidanceCreate,
    LetterGuidanceUpdate,
    LetterGuidanceResponse
)
from ..services.letter_service import LetterService

router = APIRouter(prefix="/letter", tags=["letter"])


# ─── Admin Guard ───────────────────────────────────────────────────────────────
async def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/analyze", response_model=LetterAnalysisResponse)
async def analyze_letter(
    request: LetterAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Analyze name and age to calculate governing letter and appropriate guidance
    
    Args:
        request: Name and age
    
    Returns:
        LetterAnalysisResponse: Analysis result with appropriate guidance
    
    Raises:
        HTTPException: If analysis fails
    """
    try:
        result = await LetterService.analyze(db, request)
        
        # Save to history
        if current_user:
            history_entry = AssessmentHistory(
                user_id=current_user.id,
                assessment_type="letter",
                input_data=request.model_dump(),
                result_data=result.model_dump()
            )
            db.add(history_entry)
            await db.commit()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dictionary", response_model=GuidanceDictionary)
async def get_guidance_dictionary(db: AsyncSession = Depends(get_db)):
    """
    Get the complete guidance dictionary (spiritual, behavioral, physical)
    
    Returns:
        GuidanceDictionary: Complete guidance dictionary
    """
    return await LetterService.get_dictionary(db)


# ─── Admin Endpoints ──────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=list[LetterGuidanceResponse])
async def get_all_letter_guidances(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Get all letter guidances for admins"""
    result = await db.execute(select(LetterGuidance).order_by(LetterGuidance.letter))
    return result.scalars().all()


@router.post("/admin/add", response_model=LetterGuidanceResponse)
async def add_letter_guidance(
    guidance: LetterGuidanceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Add a new letter guidance"""
    # Check if letter already exists
    existing = await db.execute(select(LetterGuidance).where(LetterGuidance.letter == guidance.letter))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="هذا الحرف موجود مسبقاً")
        
    db_guidance = LetterGuidance(**guidance.model_dump())
    db.add(db_guidance)
    await db.commit()
    await db.refresh(db_guidance)
    return db_guidance


@router.put("/admin/update/{guidance_id}", response_model=LetterGuidanceResponse)
async def update_letter_guidance(
    guidance_id: int,
    guidance_update: LetterGuidanceUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update an existing letter guidance"""
    result = await db.execute(select(LetterGuidance).where(LetterGuidance.id == guidance_id))
    db_guidance = result.scalar_one_or_none()
    
    if not db_guidance:
        raise HTTPException(status_code=404, detail="توجيه الحرف غير موجود")
        
    update_data = guidance_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_guidance, key, value)
        
    await db.commit()
    await db.refresh(db_guidance)
    return db_guidance


@router.delete("/admin/delete/{guidance_id}")
async def delete_letter_guidance(
    guidance_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete a letter guidance"""
    result = await db.execute(select(LetterGuidance).where(LetterGuidance.id == guidance_id))
    db_guidance = result.scalar_one_or_none()
    
    if not db_guidance:
        raise HTTPException(status_code=404, detail="توجيه الحرف غير موجود")
        
    await db.delete(db_guidance)
    await db.commit()
    return {"message": "تم حذف توجيه الحرف بنجاح"}
