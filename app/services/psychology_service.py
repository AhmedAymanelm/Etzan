from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.psychology import Question, QuestionnaireResponse, AssessmentResult
from ..models.question import AssessmentQuestion


class PsychologyService:
    """Business logic service for psychology assessment"""
    
    LEVEL_MESSAGES = {
        "حالة مستقرة": (
            "حالتك النفسية مستقرة بشكل عام. استمر في الحفاظ على نمط حياة صحي، "
            "ولا تتردد في طلب الدعم عند الحاجة."
        ),
        "ضغط نفسي خفيف": (
            "تمر بفترة من الضغط النفسي الخفيف. حاول أخذ فترات راحة، "
            "ومارس أنشطة تساعدك على الاسترخاء مثل المشي أو التأمل. "
            "إذا استمرت الحالة، يُنصح باستشارة متخصص."
        ),
        "اضطراب مزاجي متوسط": (
            "تشير النتيجة إلى وجود اضطراب مزاجي متوسط. "
            "يُنصح بشدة بالتحدث مع أخصائي نفسي أو معالج للحصول على الدعم المناسب. "
            "لا تتردد في طلب المساعدة، فهي خطوة إيجابية نحو التحسن."
        ),
        "اضطراب مزاجي مرتفع – يُنصح بتقييم متخصص": (
            "النتيجة تشير إلى اضطراب مزاجي مرتفع. "
            "من المهم جدًا أن تطلب مساعدة متخصصة في أقرب وقت ممكن. "
            "تواصل مع أخصائي نفسي أو طبيب نفسي لتقييم شامل ووضع خطة علاجية مناسبة. "
            "صحتك النفسية أولوية."
        )
    }
    
    @classmethod
    async def get_questionnaire_from_db(cls, db: AsyncSession) -> QuestionnaireResponse:
        """Return questionnaire with questions from database"""
        result = await db.execute(
            select(AssessmentQuestion)
            .where(
                AssessmentQuestion.assessment_type == "psychology",
                AssessmentQuestion.is_active == True
            )
            .order_by(AssessmentQuestion.order_index)
        )
        db_questions = result.scalars().all()
        
        if not db_questions:
            raise ValueError("No psychology questions found in database. Please seed questions first.")
        
        questions = [
            Question(id=q.id, text=q.text, options=q.options)
            for q in db_questions
        ]
        
        return QuestionnaireResponse(
            title="تقييم الحالة النفسية",
            description="اختر الإجابة الأقرب لك خلال الأسبوع الأخير",
            questions=questions
        )
    
    @classmethod
    def calculate_assessment(cls, answers: List[int]) -> AssessmentResult:
        """Calculate result and determine level with appropriate message.
        
        Uses percentage-based scoring to support dynamic question counts.
        Each answer is 1-3, so:
          - min possible score = num_questions * 1
          - max possible score = num_questions * 3
        """
        num_questions = len(answers)
        score = sum(answers)
        
        # Calculate percentage (0-100)
        min_score = num_questions
        max_score = num_questions * 3
        if max_score > min_score:
            percentage = ((score - min_score) / (max_score - min_score)) * 100
        else:
            percentage = 0
        
        if percentage <= 25:
            level = "حالة مستقرة"
        elif percentage <= 50:
            level = "ضغط نفسي خفيف"
        elif percentage <= 75:
            level = "اضطراب مزاجي متوسط"
        else:
            level = "اضطراب مزاجي مرتفع – يُنصح بتقييم متخصص"
        
        message = cls.LEVEL_MESSAGES[level]
        
        supportive_messages = []
        
        # Supportive messages based on individual answers (safe index checks)
        if len(answers) > 0 and answers[0] >= 2:
            supportive_messages.append(
                "النوم الجيد أساس صحتك النفسية. حاول تهيئة بيئة نوم هادئة، "
                "وتجنب الشاشات قبل النوم بساعة على الأقل."
            )
        
        if len(answers) > 2 and answers[2] >= 2:
            supportive_messages.append(
                "القلق والتوتر طبيعيان، لكن يمكن التحكم بهما. "
                "جرّب تمارين التنفس العميق أو المشي في الطبيعة."
            )
        
        if len(answers) > 4 and answers[4] >= 2:
            supportive_messages.append(
                "التفكير الزائد مرهق. حاول كتابة أفكارك أو التحدث مع شخص تثق به. "
                "لا تحمل كل شيء بمفردك."
            )
        
        if len(answers) > 6 and answers[6] >= 2:
            supportive_messages.append(
                "نظرتك لنفسك مهمة جدًا. تذكر إنجازاتك ونقاط قوتك. "
                "أنت أفضل مما تظن، وتستحق الحب والتقدير."
            )
        
        return AssessmentResult(
            score=score,
            level=level,
            message=message,
            supportive_messages=supportive_messages
        )
