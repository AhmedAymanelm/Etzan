from typing import List, Dict, Tuple
from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.neuroscience import (
    NeuroscienceQuestion,
    NeuroscienceQuestionnaireResponse,
    NeuroscienceScores,
    NeuroscienceAssessmentResult
)
from ..models.question import AssessmentQuestion


class NeuroscienceService:
    """Business logic service for neuroscience assessment"""
    
    PATTERN_NAMES = {
        "A": "Fight",
        "B": "Flight",
        "C": "Freeze",
        "D": "Fawn"
    }
    
    PATTERN_DESCRIPTIONS = {
        "Fight": (
            "A – حدود / حسم (Fight)\n\n"
            "1) لما بتحس إن في ضغط أو تهديد، أول رد فعل عندك بيكون إنك تقف وتواجه بقوة وحسم.\n"
            "2) تميل إنك تقول \"كفاية\" بسرعة، وتحط حدود واضحة لما تحس إن حد بيضغط عليك أو بيتجاوز.\n"
            "3) طاقتَك في الأزمات بتتحول لاندفاع، حزم، ورغبة قوية في تغيير الواقع فورًا.\n"
            "4) جواك صوت بيحب يحميك عن طريق السيطرة على الموقف وعدم قبول الإحساس بالضعف أو العجز."
        ),
        "Flight": (
            "B – حركة / فعل (Flight)\n\n"
            "1) لما التوتر يعلى، أول حاجة بتيجي في بالك إنك تتحرك، تغيّر مكانك، أو تشغل نفسك في أفعال كثيرة.\n"
            "2) صعب تقعد في مكانك وأنت قلق، تميل للهروب للأمام، للشغل الزيادة، أو للتفكير الزائد عشان ما تحسش بالألم.\n"
            "3) بتحب تبقي دايمًا في حركة، كأن الحل بالنسبة لك دايمًا هو: \"أعمل حاجة بسرعة قبل ما الموضوع يكبر.\"\n"
            "4) في الأوقات اللي بتحس فيها بعدم الأمان، تلقائيًا تدور على مخرج، فكرة جديدة، أو طريق تهرب بيه من الموقف."
        ),
        "Freeze": (
            "C – انسحاب / مراقبة (Freeze)\n\n"
            "1) لما تحصل حاجة تضغطك بقوة، ممكن تلاقي نفسك ساكت، متجمّد، أو مش عارف تاخد قرار.\n"
            "2) تميل إنك تقف تراقب المشهد من بعيد بدل ما تدخل فيه، كأنك متوقف مؤقتًا لحد ما الخطر يعدّي.\n"
            "3) أحيانًا تحس إنك \"مفصول\" شوية عن اللي بيحصل حواليك، عشان تقدر تستوعب وتفهم بهدوء.\n"
            "4) في لحظات التوتر، ممكن تحس إن جسمك أو تفكيرك بطّأ فجأة، كأنك محتاج توقف الدنيا ثواني قبل أي خطوة."
        ),
        "Fawn": (
            "D – تهدئة / احتواء (Fawn)\n\n"
            "1) لما الجو يتوتر، تميل تلقائيًا إنك تهدي الناس، تصلّح الجو، وتخلي الكل مرتاح حتى لو على حساب نفسك.\n"
            "2) مهم عندك جدًا إن العلاقات تفضل هادية، فتسمح أحيانًا بأشياء ما تعجبكش عشان ما يحصلش صدام.\n"
            "3) أول رد فعل ليك في الخلاف هو: \"إزاي أهدّي الموقف؟ إزاي أرضّي الشخص اللي قدامي؟\"\n"
            "4) تفضّل إنك تحافظ على القرب والانسجام، حتى لو احتجت تقلل من احتياجاتك أو ما تعبّرش عن ضيقك كاملًا."
        )
    }
    
    # ── Fallback questions removed — seeded in DB via seed_default_questions() ──
    
    @classmethod
    async def get_questionnaire_from_db(cls, db: AsyncSession) -> NeuroscienceQuestionnaireResponse:
        """Return questionnaire with questions from database"""
        result = await db.execute(
            select(AssessmentQuestion)
            .where(
                AssessmentQuestion.assessment_type == "neuroscience",
                AssessmentQuestion.is_active == True
            )
            .order_by(AssessmentQuestion.order_index)
        )
        db_questions = result.scalars().all()
        
        if not db_questions:
            raise ValueError("No neuroscience questions found in database. Please seed questions first.")
        
        import json
        questions = [
            NeuroscienceQuestion(
                id=q.id,
                text=q.text,
                options=json.loads(q.options) if isinstance(q.options, str) else q.options,
                options_text=json.loads(q.options_text) if isinstance(q.options_text, str) else (q.options_text or {})
            )
            for q in db_questions
        ]
        
        return NeuroscienceQuestionnaireResponse(
            title="تقييم الجهاز العصبي",
            description="اختر الإجابة الأقرب لحالتك الآن",
            questions=questions
        )
    
    @classmethod
    def _count_answers(cls, answers: List[str]) -> Dict[str, int]:
        """Count occurrences of each answer (case-insensitive)"""
        upper_answers = [str(a).upper() for a in answers]
        counts = Counter(upper_answers)
        return {
            "A": counts.get("A", 0),
            "B": counts.get("B", 0),
            "C": counts.get("C", 0),
            "D": counts.get("D", 0)
        }
    
    @classmethod
    def _get_sorted_patterns(cls, scores: Dict[str, int]) -> List[Tuple[str, int]]:
        """Sort patterns by score descending"""
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    @classmethod
    def _determine_dominant_and_secondary(
        cls, 
        scores: Dict[str, int]
    ) -> Tuple[str, str, bool]:
        """
        Determine dominant and secondary patterns
        
        Returns:
            Tuple[dominant, secondary, strong_secondary]
        """
        sorted_patterns = cls._get_sorted_patterns(scores)
        top_score = sorted_patterns[0][1]
        tied_patterns = [p for p, s in sorted_patterns if s == top_score]
        
        if len(tied_patterns) > 1:
            pattern_names = [cls.PATTERN_NAMES[p] for p in tied_patterns]
            dominant = "Mixed " + "/".join(pattern_names)
            remaining_patterns = [
                (p, s) for p, s in sorted_patterns if p not in tied_patterns
            ]
            if remaining_patterns:
                secondary = cls.PATTERN_NAMES[remaining_patterns[0][0]]
            else:
                secondary = "None"
            strong_secondary = False
        else:
            dominant = cls.PATTERN_NAMES[sorted_patterns[0][0]]
            secondary = cls.PATTERN_NAMES[sorted_patterns[1][0]]
            diff = sorted_patterns[0][1] - sorted_patterns[1][1]
            strong_secondary = diff <= 1
        
        return dominant, secondary, strong_secondary
    
    @classmethod
    def _get_description(cls, dominant: str) -> str:
        """Get appropriate description for the pattern"""
        if dominant.startswith("Mixed"):
            patterns = dominant.replace("Mixed ", "").split("/")
            first_pattern = patterns[0]
            return cls.PATTERN_DESCRIPTIONS.get(
                first_pattern, 
                cls.PATTERN_DESCRIPTIONS["Fight"]
            )
        return cls.PATTERN_DESCRIPTIONS.get(
            dominant, 
            cls.PATTERN_DESCRIPTIONS["Fight"]
        )
    
    @classmethod
    def calculate_assessment(cls, answers: List[str]) -> NeuroscienceAssessmentResult:
        """Calculate result and determine neural patterns"""
        scores = cls._count_answers(answers)
        dominant, secondary, strong_secondary = cls._determine_dominant_and_secondary(
            scores
        )
        description = cls._get_description(dominant)
        
        return NeuroscienceAssessmentResult(
            scores=NeuroscienceScores(**scores),
            dominant=dominant,
            secondary=secondary,
            strong_secondary=strong_secondary,
            description=description
        )
