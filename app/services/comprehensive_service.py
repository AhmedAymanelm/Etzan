from typing import Dict, Any
from ..services.psychology_service import PsychologyService
from ..services.neuroscience_service import NeuroscienceService
from ..services.astrology_service import AstrologyService
from ..models.astrology import AstrologyRequest
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from app.utils.settings_helper import get_env_or_db, get_random_setting_item

load_dotenv()


class ComprehensiveService:
    """Service for comprehensive multi-assessment analysis"""
    
    @classmethod
    async def analyze_all(
        cls,
        name: str,
        psychology_answers: list,
        neuroscience_answers: list,
        birth_date: str,
        day_type: str = "today",
        birth_time: str = None,
        city_of_birth: str = None,
        latitude: float = None,
        longitude: float = None
    ) -> Dict[str, Any]:
        
        psychology_result = PsychologyService.calculate_assessment(psychology_answers)
        
        neuroscience_result = NeuroscienceService.calculate_assessment(neuroscience_answers)
        
        base_pattern = neuroscience_result.dominant.replace("Mixed ", "").split("/")[0].strip()
        music_url = await get_random_setting_item(f"neuro_music_{base_pattern.lower()}")
        
        astrology_request = AstrologyRequest(
            name=name,
            birth_date=birth_date,
            day_type=day_type,
            birth_time=birth_time,
            birth_location=city_of_birth or "",
            latitude=latitude,
            longitude=longitude
        )
        astrology_result = await AstrologyService.analyze(astrology_request)
        
        comprehensive_data = {
            "name": name,
            "type": "comprehensive",
            
            "psychology": {
                "score": psychology_result.score,
                "level": psychology_result.level,
                "message": psychology_result.message,
                "supportive_messages": psychology_result.supportive_messages
            },
            
            "neuroscience": {
                "dominant": neuroscience_result.dominant,
                "secondary": neuroscience_result.secondary,
                "strong_secondary": neuroscience_result.strong_secondary,
                "description": neuroscience_result.description,
                "background_music_url": music_url,
                "scores": {
                    "Fight": neuroscience_result.scores.A,
                    "Flight": neuroscience_result.scores.B,
                    "Freeze": neuroscience_result.scores.C,
                    "Fawn": neuroscience_result.scores.D
                }
            },
            
            "astrology": {
                "sun_sign": astrology_result.sun_sign,
                "ascendant": astrology_result.ascendant,
                "psychological_state": astrology_result.psychological_state,
                "emotional_state": astrology_result.emotional_state,
                "mental_state": astrology_result.mental_state,
                "physical_state": astrology_result.physical_state,
                "luck_level": astrology_result.luck_level,
                "lucky_color": astrology_result.lucky_color,
                "lucky_number": astrology_result.lucky_number,
                "compatibility": astrology_result.compatibility,
                "advice": astrology_result.advice,
                "warning": astrology_result.warning
            }
        }
        
        return comprehensive_data
    
    @classmethod
    async def generate_comprehensive_report(
        cls,
        name: str,
        psychology_result: Dict[str, Any],
        neuroscience_result: Dict[str, Any],
        astrology_result: Dict[str, Any],
        letter_result: Dict[str, Any] = None,
        model: str = "gpt-4o",
        temperature: float = 0.8
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive AI analysis report from pre-computed results.
        Takes results from individual assessments and creates unified insights.
        """
        
        sciences_count = "أربعة علوم (علم النفس، علم الأعصاب، الأبراج، علم الحروف)" if letter_result else "ثلاثة علوم (علم النفس، علم الأعصاب، الأبراج)"
        
        system_prompt = f"""أنت خبير متخصص في التحليل النفسي والعصبي والفلكي وعلم الحروف الشامل.
مهمتك هي دمج النتائج من {sciences_count} وإنشاء تقرير متكامل وعميق وشخصي.

أسلوبك:
- دافئ، محترف، مبني على الأدلة، ومتعاطف للغاية
- تتحدث مباشرة إلى الشخص باستخدام "أنت"
- تجمع بين الحكمة القديمة والرؤى الحديثة
- تقدم نصائح عملية قابلة للتطبيق
- لغة عربية فصحى مبسطة وسلسة"""

        user_prompt = f"""
قم بإنشاء تقرير تحليلي شامل للشخص التالي:

**الاسم:** {name}

---

### نتائج التقييم النفسي:
- **النتيجة:** {psychology_result.get('score', 'N/A')}/21
- **المستوى:** {psychology_result.get('level', 'N/A')}
- **التحليل:** {psychology_result.get('message', 'N/A')}
- **رسائل داعمة:** {', '.join(psychology_result.get('supportive_messages', []))}

---

### نتائج التقييم العصبي:
- **النمط السائد:** {neuroscience_result.get('dominant', 'N/A')}
- **النمط الثانوي:** {neuroscience_result.get('secondary', 'N/A')}
- **قوة النمط الثانوي:** {'نعم' if neuroscience_result.get('strong_secondary') else 'لا'}
- **الوصف:** {neuroscience_result.get('description', 'N/A')}
- **الدرجات:**
  - Fight (المواجهة): {neuroscience_result.get('scores', {}).get('Fight', 'N/A')}
  - Flight (الهروب): {neuroscience_result.get('scores', {}).get('Flight', 'N/A')}
  - Freeze (التجمد): {neuroscience_result.get('scores', {}).get('Freeze', 'N/A')}
  - Fawn (الإرضاء): {neuroscience_result.get('scores', {}).get('Fawn', 'N/A')}

---

### نتائج التحليل الفلكي:
- **البرج الشمسي:** {astrology_result.get('sun_sign', 'N/A')}
- **الطالع:** {astrology_result.get('ascendant', 'N/A')}
- **الحالة النفسية:** {astrology_result.get('psychological_state', 'N/A')}
- **الحالة العاطفية:** {astrology_result.get('emotional_state', 'N/A')}
- **الحالة الذهنية:** {astrology_result.get('mental_state', 'N/A')}
- **الحالة الجسدية:** {astrology_result.get('physical_state', 'N/A')}
- **مستوى الحظ:** {astrology_result.get('luck_level', 'N/A')}
- **اللون المحظوظ:** {astrology_result.get('lucky_color', 'N/A')}
- **الرقم المحظوظ:** {astrology_result.get('lucky_number', 'N/A')}
- **التوافق البرجي:** {astrology_result.get('compatibility', 'N/A')}
- **النصيحة:** {astrology_result.get('advice', 'N/A')}
- **التحذير:** {astrology_result.get('warning', 'N/A')}

---

{'### نتائج تحليل علم الحروف:' if letter_result else ''}
{f"""- **الحرف الحاكم:** {letter_result.get('governing_letter', 'N/A')}
- **المرحلة:** {letter_result.get('stage', 'N/A')}
- **عدد الحروف:** {letter_result.get('letters_count', 'N/A')}
- **نوع التوجيه:** {letter_result.get('guidance_type', 'N/A')}
- **التوجيه:** {letter_result.get('guidance', 'N/A')}

---
""" if letter_result else ''}

### المطلوب منك:

اكتب تقريراً شاملاً متدفقاً **بدون أي عناوين أو أرقام أو نقاط أو تقسيمات** — فقرات متصلة فقط تُقرأ كرسالة شخصية حميمة.

التقرير يجب أن يغطي هذه المحاور مدمجةً بشكل سلس داخل الفقرات دون الإشارة الصريحة إليها:

- ابدأ بمقدمة ترحيبية دافئة تُشعر الشخص بأنك تعرفه جيداً
- عرّفه بكل نتائج العلوم {'الأربعة' if letter_result else 'الثلاثة'} بشكل مفهوم وضمن السياق:
  برجه الشمسي ({astrology_result.get('sun_sign', '')}) وما يعنيه، وطالعه الفلكي ({astrology_result.get('ascendant', '')}) وكيف يُكمل برجه الشمسي، وأنماطه العصبية الأربعة بالترتيب (Fight ثم Flight ثم Freeze ثم Fawn) وما تكشفه عن طريقة استجابته، ومستوى صحته النفسية ودرجته، {'وحرفه الحاكم ومرحلته في علم الحروف وما يدل عليه سلوكياً' if letter_result else ''}
- اربط التقاطعات بين العلوم في صورة منسجمة واحدة
- فسّر لماذا يشعر بهذه الطريقة وما الجذور العميقة لأنماطه
- قدّم توصيات عملية ملموسة تستخدم لونه المحظوظ ({astrology_result.get('lucky_color', '')}) ورقمه المحظوظ ({astrology_result.get('lucky_number', '')}) والتوافق البرجي ({astrology_result.get('compatibility', '')})
- اختم برسالة تمكينية قوية لا تُنسى

### إرشادات الأسلوب الصارمة:
- لا عناوين، لا أرقام، لا نقاط، لا نص غامق — فقرات متصلة فقط
- تحدث كصديق حكيم يعرف الشخص جيداً
- استخدم الاسم ({name}) عدة مرات بشكل طبيعي
- استخدم "أنت" لخلق الحميمية
- لا تترك أي معلومة من النتائج دون ذكرها وتفسيرها ضمن السياق
- الطول الإجمالي: 600-800 كلمة

اكتب التقرير الكامل الآن، جاهزاً للقراءة مباشرة.
"""
        
        try:
            openai_key = await get_env_or_db("openai_api_key")
            db_model = await get_env_or_db("openai_model")
            actual_model = db_model if db_model else model
            
            client = AsyncOpenAI(api_key=openai_key)
            
            response = await client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2500
            )
            
            comprehensive_report = response.choices[0].message.content.strip()
            
            return {
                "name": name,
                "type": "تحليل شامل",
                "report": comprehensive_report,
                "results_summary": {
                    "psychology": psychology_result,
                    "neuroscience": neuroscience_result,
                    "astrology": astrology_result,
                    "letter": letter_result
                },
                "status": "success",
                "message": "تم إنشاء التقرير الشامل بنجاح"
            }
            
        except Exception as e:
            return {
                "name": name,
                "type": "تحليل شامل",
                "report": cls._get_fallback_report(name, psychology_result, neuroscience_result, astrology_result, letter_result),
                "results_summary": {
                    "psychology": psychology_result,
                    "neuroscience": neuroscience_result,
                    "astrology": astrology_result,
                    "letter": letter_result
                },
                "status": "fallback",
                "message": f"تم استخدام التقرير الاحتياطي بسبب: {str(e)}"
            }
    
    @classmethod
    def _get_fallback_report(
        cls,
        name: str,
        psychology_result: Dict[str, Any],
        neuroscience_result: Dict[str, Any],
        astrology_result: Dict[str, Any],
        letter_result: Dict[str, Any] = None
    ) -> str:
        """Generate a simple fallback report if AI generation fails"""
        
        letter_section = f"""
**تحليل علم الحروف:**
حرفك الحاكم هو "{letter_result.get('governing_letter', 'غير معروف')}" وأنت في مرحلة {letter_result.get('stage', 'غير معروفة')}.
نوع التوجيه: {letter_result.get('guidance_type', 'عام')}
{letter_result.get('guidance', '')}
""" if letter_result else ""
        
        return f"""
مرحباً {name}، هذا تقريرك الشامل المتكامل.

**التحليل النفسي:**
مستوى صحتك النفسية هو {psychology_result.get('level', 'متوسط')} بدرجة {psychology_result.get('score', 0)} من 21. 
{psychology_result.get('message', '')}

**التحليل العصبي:**
نمطك السائد هو {neuroscience_result.get('dominant', 'غير معروف')}، مع نمط ثانوي {neuroscience_result.get('secondary', 'غير معروف')}.
{neuroscience_result.get('description', '')}

**التحليل الفلكي:**
أنت من مواليد برج {astrology_result.get('sun_sign', 'غير معروف')}{f" وطالعك {astrology_result.get('ascendant', '')}" if astrology_result.get('ascendant') else ""}.
حالتك النفسية: {astrology_result.get('psychological_state', 'متوازنة')}
حالتك العاطفية: {astrology_result.get('emotional_state', 'مستقرة')}
مستوى حظك: {astrology_result.get('luck_level', 'جيد')}
{letter_section}
**النصائح:**
{astrology_result.get('advice', 'كن إيجابياً ومتفائلاً')}

**تحذيرات:**
{astrology_result.get('warning', 'لا توجد تحذيرات خاصة')}

تذكر أن هذا التحليل هو دليل فقط، وأنت من يصنع مستقبلك بإرادتك وجهدك. ثق بنفسك وكن قوياً!
"""
