import math
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.letter import LetterAnalysisRequest, LetterAnalysisResponse, GuidanceDictionary
from ..models.letter_guidance import LetterGuidance


class LetterService:
    """Business logic service for letter science"""
    
    DEPENDENT_LETTERS = ["د", "ذ"]
    
    @classmethod
    def clean_name(cls, name: str) -> str:
        """Clean name: remove spaces and keep only letters"""

        cleaned = name.replace(" ", "").strip()
        return cleaned
    
    @classmethod
    def calculate_stage_and_letter(cls, name: str, age: int) -> Tuple[int, str, int]:
        """
        Calculate stage and governing letter
        
        Returns:
            Tuple[int, str, int]: (stage, governing_letter, letters_count)
        """

        cleaned_name = cls.clean_name(name)
        letters_count = len(cleaned_name)
        

        if letters_count == 1:
            return 1, cleaned_name[0], letters_count
        

        if letters_count == 2:

            duration_per_letter = 20
            stage = min(math.ceil(age / duration_per_letter), letters_count)
            governing_letter = cleaned_name[stage - 1]
            return stage, governing_letter, letters_count
        

        if age < 20:
            stage = 1
        else:
            years_after_20 = age - 20
            stage = math.ceil(years_after_20 / 15) + 1
        

        if stage > letters_count:
            duration_per_letter = age / letters_count
            stage = math.ceil(age / duration_per_letter)
            stage = min(stage, letters_count)
        
        governing_letter = cleaned_name[stage - 1]
        return stage, governing_letter, letters_count
    
    @classmethod
    def apply_dependency_rule(cls, governing_letter: str, name: str, stage: int) -> Tuple[str, bool]:
        """
        Apply dependency rule
        
        Returns:
            Tuple[str, bool]: (final_letter, is_dependent)
        """
        if governing_letter in cls.DEPENDENT_LETTERS:

            if stage > 1:
                cleaned_name = cls.clean_name(name)
                previous_letter = cleaned_name[stage - 2]
                return previous_letter, True
            else:

                return governing_letter, True
        
        return governing_letter, False
    
    @classmethod
    async def get_guidance(cls, db: AsyncSession, letter: str) -> Tuple[str, str]:
        """
        Get appropriate guidance for the letter from the database
        
        Returns:
            Tuple[str, str]: (guidance_type, guidance_text)
        """
        result = await db.execute(
            select(LetterGuidance).where(LetterGuidance.letter == letter)
        )
        guidance_obj = result.scalar_one_or_none()
        
        if guidance_obj:
            return guidance_obj.guidance_type, guidance_obj.guidance_text
            
        return "dependent", f"لا يوجد توجيه محدد للحرف '{letter}'"
    
    @classmethod
    async def analyze(cls, db: AsyncSession, request: LetterAnalysisRequest) -> LetterAnalysisResponse:
        

        stage, governing_letter, letters_count = cls.calculate_stage_and_letter(
            request.name, 
            request.age
        )
        

        final_letter, is_dependent = cls.apply_dependency_rule(
            governing_letter, 
            request.name, 
            stage
        )
        

        guidance_type, guidance = await cls.get_guidance(db, final_letter)
        

        return LetterAnalysisResponse(
            name=request.name,
            age=request.age,
            letters_count=letters_count,
            stage=stage,
            governing_letter=final_letter,
            is_dependent=is_dependent,
            guidance_type=guidance_type,
            guidance=guidance
        )
    
    @classmethod
    async def get_dictionary(cls, db: AsyncSession) -> GuidanceDictionary:
        """Return the complete guidance dictionary"""
        result = await db.execute(select(LetterGuidance))
        guidances = result.scalars().all()
        
        spiritual = {g.letter: g.guidance_text for g in guidances if g.guidance_type == "spiritual"}
        behavioral = {g.letter: g.guidance_text for g in guidances if g.guidance_type == "behavioral"}
        physical = {g.letter: g.guidance_text for g in guidances if g.guidance_type == "physical"}
        
        return GuidanceDictionary(
            spiritual=spiritual,
            behavioral=behavioral,
            physical=physical
        )
