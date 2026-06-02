import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from timezonefinder import TimezoneFinder
import pytz

from ..models.astrology import AstrologyRequest, AstrologyResponse
from app.utils.settings_helper import get_env_or_db

class AstrologyService:
    """Business logic service for astrology - dynamic analysis using OpenAI"""
    
    ASTROLOGY_API_BASE_DEFAULT = "https://api.astrology-api.io/api/v3"

    ZODIAC_SIGNS_AR = {
        "aries": "الحمل", "taurus": "الثور", "gemini": "الجوزاء", "cancer": "السرطان",
        "leo": "الأسد", "virgo": "العذراء", "libra": "الميزان", "scorpio": "العقرب",
        "sagittarius": "القوس", "capricorn": "الجدي", "aquarius": "الدلو", "pisces": "الحوت",
        "ari": "الحمل", "tau": "الثور", "gem": "الجوزاء", "can": "السرطان",
        "vir": "العذراء", "lib": "الميزان", "sco": "العقرب",
        "sag": "القوس", "cap": "الجدي", "aqu": "الدلو", "pis": "الحوت"
    }

    DAILY_LUCKY_COLORS_AR = [
        "أخضر",
        "أزرق",
        "ذهبي",
        "فضي",
        "أبيض",
        "أحمر",
        "بنفسجي",
        "برتقالي",
        "وردي",
    ]

    @classmethod
    def _compute_daily_lucky_values(cls, transit_planets: Dict[str, Any], target_date: str) -> Dict[str, str]:
        """Compute deterministic daily lucky values from transit data and target date."""
        seed_parts = [target_date]
        for planet_name in sorted(transit_planets.keys()):
            planet_data = transit_planets.get(planet_name, {})
            zodiac = str(planet_data.get("zodiac", ""))
            degree = str(planet_data.get("degree", ""))
            seed_parts.append(f"{planet_name}:{zodiac}:{degree}")

        seed_text = "|".join(seed_parts)
        checksum = sum(ord(ch) for ch in seed_text)

        lucky_number = str((checksum % 9) + 1)
        lucky_color = cls.DAILY_LUCKY_COLORS_AR[checksum % len(cls.DAILY_LUCKY_COLORS_AR)]

        return {
            "lucky_number": lucky_number,
            "lucky_color": lucky_color,
        }

    @classmethod
    async def _geocode_location(cls, location: str) -> tuple[Optional[float], Optional[float]]:
        """Geocode city/country string to latitude and longitude using Nominatim."""
        try:
            import urllib.parse
            query = urllib.parse.quote(location)
            headers = {"User-Agent": "BaytAlHayatAstrologyApp/1.0"}
            url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        return float(data[0].get("lat", 0.0)), float(data[0].get("lon", 0.0))
        except Exception as e:
            print(f"Geocoding error for {location}: {e}")
        return None, None

    @classmethod
    def _extract_planets(cls, api_response: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract and normalize planet positions from astrology-api response."""
        planets_data: Dict[str, Dict[str, Any]] = {}
        if not api_response or "data" not in api_response:
            return planets_data

        positions = api_response.get("data", {}).get("positions", [])
        for planet in positions:
            planet_name = planet.get("name", "")
            if not planet_name:
                continue
            zodiac = planet.get("sign", "")
            degree = planet.get("degree", 0.0)
            planets_data[planet_name] = {
                "zodiac": zodiac,
                "degree": round(degree, 2),
            }
        return planets_data

    @classmethod
    def _extract_ascendant(cls, cusps_response: Dict[str, Any]) -> str:
        """Extract ascendant sign from house-cusps API response (house 1)."""
        if not cusps_response or "data" not in cusps_response:
            return ""
        cusps = cusps_response.get("data", {}).get("cusps", [])
        for cusp in cusps:
            if cusp.get("house") == 1:
                return cusp.get("sign", "")
        return ""

    @classmethod
    def get_zodiac_sign(cls, birth_date_str: str) -> str:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
        month = birth_date.month
        day = birth_date.day
        
        if (month == 3 and day >= 21) or (month == 4 and day <= 19): return "aries"
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20): return "taurus"
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20): return "gemini"
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22): return "cancer"
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22): return "leo"
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22): return "virgo"
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22): return "libra"
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21): return "scorpio"
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21): return "sagittarius"
        elif (month == 12 and day >= 22) or (month == 1 and day <= 19): return "capricorn"
        elif (month == 1 and day >= 20) or (month == 2 and day <= 18): return "aquarius"
        else: return "pisces"

    @classmethod
    async def fetch_horoscope(cls, sign: str, day: str, birth_date_str: str, 
                               birth_time: Optional[str] = None, 
                               latitude: Optional[float] = None, 
                               longitude: Optional[float] = None) -> Dict[str, Any]:
        """Fetch natal birth data and daily transits separately."""
        
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
        
        if birth_time:
            try:
                time_parts = birth_time.split(":")
                birth_hour = int(time_parts[0])
                birth_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            except:
                birth_hour = 12
                birth_minute = 0
        else:
            birth_hour = 12
            birth_minute = 0
        
        if latitude is None: latitude = 30.0
        if longitude is None: longitude = 31.0
        
        timezone_val = "UTC"
        try:
            tf = TimezoneFinder()
            tz_str = tf.timezone_at(lat=latitude, lng=longitude)
            if tz_str:
                timezone_val = tz_str
        except Exception as e:
            print(f"Timezone calculation error: {e}")
        
        if day == "today": target_date = datetime.now()
        elif day == "tomorrow": target_date = datetime.now() + timedelta(days=1)
        else: target_date = datetime.now() - timedelta(days=1)
        
        api_base = await get_env_or_db("astrology_api_base") or cls.ASTROLOGY_API_BASE_DEFAULT
        api_key = await get_env_or_db("astrology_api_key")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        natal_payload = {
            "subject": {
                "name": "User",
                "birth_data": {
                    "year": birth_date.year,
                    "month": birth_date.month,
                    "day": birth_date.day,
                    "hour": birth_hour,
                    "minute": birth_minute,
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone_val
                }
            }
        }

        # Daily transits are computed from target date, independent from natal birth date.
        transit_payload = {
            "subject": {
                "name": "TransitDate",
                "birth_data": {
                    "year": target_date.year,
                    "month": target_date.month,
                    "day": target_date.day,
                    "hour": 12,
                    "minute": 0,
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone_val
                }
            }
        }
        
        try:
            import asyncio
            async with httpx.AsyncClient(timeout=15.0) as client:
                pos_url = f"{api_base}/data/positions"
                cusps_url = f"{api_base}/data/house-cusps"

                natal_positions_req = client.post(pos_url, json=natal_payload, headers=headers)
                natal_cusps_req = client.post(cusps_url, json=natal_payload, headers=headers)
                transit_positions_req = client.post(pos_url, json=transit_payload, headers=headers)

                natal_pos_res, natal_cusps_res, transit_pos_res = await asyncio.gather(
                    natal_positions_req,
                    natal_cusps_req,
                    transit_positions_req,
                )

                natal_pos_res.raise_for_status()
                transit_pos_res.raise_for_status()

                natal_positions_data = natal_pos_res.json()
                natal_cusps_data = natal_cusps_res.json() if natal_cusps_res.status_code == 200 else {}
                transit_positions_data = transit_pos_res.json()

                natal_planets = cls._extract_planets(natal_positions_data)
                transit_planets = cls._extract_planets(transit_positions_data)
                ascendant_sign = cls._extract_ascendant(natal_cusps_data)

                if not transit_planets:
                    raise Exception("No transit positions in API response")

                print(
                    f"[ASTRO] Natal planets: {len(natal_planets)}, Transits: {len(transit_planets)}, "
                    f"Ascendant: {ascendant_sign or 'N/A'}, Day: {target_date.date().isoformat()}"
                )

                return {
                    "natal_planets": natal_planets,
                    "transit_planets": transit_planets,
                    "ascendant": ascendant_sign,
                    "target_date": target_date.date().isoformat(),
                }
        except Exception as e:
            print(f"[ERROR] Astrology API error: {str(e)}")
            zodiac_title = sign.title()
            fallback_natal = {
                "Sun": {"zodiac": zodiac_title, "degree": 15.0},
                "Moon": {"zodiac": "Cancer", "degree": 10.0},
                "Mercury": {"zodiac": "Gemini", "degree": 5.0},
                "Venus": {"zodiac": "Taurus", "degree": 20.0},
                "Mars": {"zodiac": "Aries", "degree": 8.0}
            }
            fallback_transits = {
                "Sun": {"zodiac": "Aries", "degree": 12.0},
                "Moon": {"zodiac": "Leo", "degree": 4.0},
                "Mercury": {"zodiac": "Pisces", "degree": 22.0},
                "Venus": {"zodiac": "Taurus", "degree": 8.0},
                "Mars": {"zodiac": "Cancer", "degree": 17.0},
            }
            return {
                "natal_planets": fallback_natal,
                "transit_planets": fallback_transits,
                "ascendant": "",
                "target_date": target_date.date().isoformat(),
            }
            
    @classmethod
    async def _generate_ai_analysis(
        cls,
        natal_planets: Dict[str, Any],
        transit_planets: Dict[str, Any],
        sun_sign_ar: str,
        ascendant_ar: str,
        target_date: str,
    ) -> Dict[str, str]:
        """Dynamic astrological analysis combining natal data and daily transits."""
        openai_api_key = await get_env_or_db("openai_api_key", "OPENAI_API_KEY")
        model = await get_env_or_db("openai_model", "OPENAI_MODEL") or "gpt-4o"
        
        if not openai_api_key:
            raise Exception("مفتاح OpenAI غير متوفر، لا يمكن توليد التحليل.")
            
        client = AsyncOpenAI(api_key=openai_api_key)
        
        natal_context_parts = []
        for name, data in natal_planets.items():
            if isinstance(data, dict):
                natal_context_parts.append(f"{name} في {data.get('zodiac')}")

        transit_context_parts = []
        for name, data in transit_planets.items():
            if isinstance(data, dict):
                transit_context_parts.append(f"{name} في {data.get('zodiac')}")

        natal_context = "، ".join(natal_context_parts)
        transit_context = "، ".join(transit_context_parts)
        
        prompt = f"""
أنت منجم فلكي محترف مبدع في تحليل تأثير (حركة الكواكب اليوم - Transits) على المستخدم.
لتجنب تضليل المستخدم، يجب التفرقة تماماً بين خريطته الشخصية (ثابتة) وحركة السماء اليوم (عابرة).

بيانات المستخدم الشخصية (Natal):
- البرج الشمسي الأساسي: {sun_sign_ar}
- الطالع: {ascendant_ar if ascendant_ar else 'غير محدد'}

تاريخ التحليل المطلوب:
{target_date}

خريطة الميلاد الأصلية (Natal Positions):
{natal_context}

حركة الكواكب الفعليّة في السماء لهذا اليوم (Current Transits):
{transit_context}

تعليمات صياغة صارمة جداً (Golden Rules):
- إياك أن تذكر اسم البرج الذي يتواجد فيه الكوكب العابر حالياً. (مثال مرفوض: "الزهرة في الثور تثير رغبتك...").
- الأسلوب الصحيح أن تصف قوة وطاقة الكوكب العابر فقط دون تحديد مكانه، (مثال صحيح: "تأثير طاقة الزهرة اليوم يعزز احتياجك للأمان...", "يدعم عبور المريخ اليوم نشاطك...").
- اربط تأثير طاقات هذه الكواكب اليوم ببرجه الأساسي ({sun_sign_ar}) بذكاء.
- الأهم: اجعل تحليل اليوم مختلفاً فعلياً حسب تاريخ التحليل {target_date} بناءً على Transits.
- اجعل التحليل تفسيرياً، مرناً، وتجنب الادعاءات الفلكية المحددة بالأبراج العابرة.

مطلوب إرجاع JSON صالح 100% يحتوي على هذه المفاتيح بالضبط فقط:
1. "psychological_state": التحليل النفسي بناءً على حركة الكواكب العابرة اليوم. (حوالي 25 كلمة)
2. "emotional_state": مراجعة العواطف وتأثير عبور الزهرة والقمر اليوم. (حوالي 25 كلمة)
3. "mental_state": تحليل التفكير والإدراك وتأثير عبور عطارد اليوم. (حوالي 25 كلمة)
4. "physical_state": النشاط والطاقة وتأثير حركة المريخ اليوم. (حوالي 25 كلمة)
5. "luck_level": اختر كلمة واحدة (مرتفع جداً، مرتفع، متوسط، منخفض) بدون تفسير مضاف.
6. "lucky_color": لون واحد حرفياً يناسب الطاقات الفلكية اليوم.
7. "lucky_number": رقم واحد فقط ملائم.
8. "compatibility": برج واحد يندمج معه بسهولة مع طاقة هذا اليوم.
9. "advice": نصيحة عملية للتناغم مع طاقة الكواكب اليوم. (حوالي 15 كلمة)
10. "warning": تحذير ذكي عن شيء محدد لتجنبه اليوم. (حوالي 15 كلمة)
"""
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a specialized astrologer REST API returning exclusively raw valid JSON objects."},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            result_text = response.choices[0].message.content
            return json.loads(result_text)
        except Exception as e:
            print(f"[ERROR] OpenAI Error in Astrology: {str(e)}")
            # Fallback
            return {
                "psychological_state": f"تأثير {sun_sign_ar} يمنحك اليوم تركيزاً عميقاً وطاقة داخلية.",
                "emotional_state": "وجود الكواكب في مواقعها الحالية يدعم استقرار علاقاتك.",
                "mental_state": "طاقة عطارد اليوم تمنحك سرعة في الإدراك وتحليل الموقف.",
                "physical_state": "المريخ يوجه طاقتك نحو الإنجاز العملي المتوازن.",
                "luck_level": "متوسط",
                "lucky_color": "أزرق",
                "lucky_number": "7",
                "compatibility": "العذراء",
                "advice": "استغل طاقتك الكامنة بذكاء ورتب أولوياتك.",
                "warning": "تجنب التسرع في ردود الأفعال واتخاذ القرارات المفاجئة."
            }

    @classmethod
    async def analyze(cls, request: AstrologyRequest) -> AstrologyResponse:
        """Analyze daily horoscope using API data combined with AI"""
        
        latitude = request.latitude
        longitude = request.longitude
        
        if (latitude is None or longitude is None) and request.city_of_birth:
            lat, lon = await cls._geocode_location(request.city_of_birth)
            if lat is not None and lon is not None:
                latitude = lat
                longitude = lon
                
        zodiac_sign_en = cls.get_zodiac_sign(request.birth_date)
        zodiac_sign_ar = cls.ZODIAC_SIGNS_AR[zodiac_sign_en]
        
        horoscope_data = await cls.fetch_horoscope(
            zodiac_sign_en, 
            request.day_type, 
            request.birth_date,
            request.birth_time,
            latitude,
            longitude
        )
        
        natal_planets = horoscope_data.get("natal_planets", {})
        transit_planets = horoscope_data.get("transit_planets", {})
        ascendant = horoscope_data.get("ascendant", "")
        target_date = horoscope_data.get("target_date", datetime.now().date().isoformat())
        ascendant_ar = cls.ZODIAC_SIGNS_AR.get(ascendant.lower(), ascendant) if ascendant else ""

        daily_lucky = cls._compute_daily_lucky_values(transit_planets, target_date)
        
        # Generate the sophisticated AI response based on real data
        ai_analysis = await cls._generate_ai_analysis(
            natal_planets,
            transit_planets,
            zodiac_sign_ar,
            ascendant_ar,
            target_date,
        )
        
        lucky_number_str = daily_lucky["lucky_number"]
        lucky_color_str = daily_lucky["lucky_color"]
        
        moon_sign_ar = ""
        if "Moon" in natal_planets:
            ms_en = natal_planets["Moon"].get("zodiac", "").lower()
            moon_sign_ar = cls.ZODIAC_SIGNS_AR.get(ms_en, ms_en)

        PLANETS_AR_MAP = {
            "Mercury": "عطارد",
            "Venus": "الزهرة",
            "Mars": "المريخ"
        }
        
        planets_dict = {}
        for p_en, p_ar in PLANETS_AR_MAP.items():
            if p_en in natal_planets:
                s_en = natal_planets[p_en].get("zodiac", "").lower()
                planets_dict[p_ar] = cls.ZODIAC_SIGNS_AR.get(s_en, s_en)
        
        return AstrologyResponse(
            name=request.name,
            sun_sign=zodiac_sign_ar,
            moon_sign=moon_sign_ar,
            ascendant=ascendant_ar,
            planets=planets_dict,
            birth_date=request.birth_date,
            day_type=request.day_type,
            psychological_state=ai_analysis.get("psychological_state", "متوازن"),
            emotional_state=ai_analysis.get("emotional_state", "مستقر"),
            mental_state=ai_analysis.get("mental_state", "مرتفع التركيز"),
            physical_state=ai_analysis.get("physical_state", "طاقة متوسطة"),
            luck_level=ai_analysis.get("luck_level", "متوسط"),
            lucky_color=lucky_color_str,
            lucky_number=lucky_number_str,
            compatibility=ai_analysis.get("compatibility", "العقرب"),
            advice=ai_analysis.get("advice", "اعتني بنفسك!"),
            warning=ai_analysis.get("warning", "تجنب المبالغة.")
        )
