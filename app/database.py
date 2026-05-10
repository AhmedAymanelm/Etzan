from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Diagnostic print (safe version)
    print("⚠️  DATABASE_URL not found in environment variables.")
    raise RuntimeError(
        "❌ DATABASE_URL is missing! \n"
        "If you are on Railway/Heroku: Go to 'Variables' and add DATABASE_URL.\n"
        "If you are Local: Check if your .env file exists and has DATABASE_URL=..."
    )

# Fix for Railway/Heroku postgres:// vs postgresql:// and adding asyncpg driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Robustly remove 'sslmode' and other incompatible params for asyncpg
if "?" in DATABASE_URL:
    base_url, query_str = DATABASE_URL.split("?", 1)
    # Remove sslmode from query string
    params = [p for p in query_str.split("&") if not p.startswith("sslmode=")]
    DATABASE_URL = base_url + ("?" + "&".join(params) if params else "")

# Masked URL for logging
masked_url = DATABASE_URL
if "@" in masked_url:
    prefix, suffix = masked_url.split("@", 1)
    if ":" in prefix:
        proto_user, _ = prefix.rsplit(":", 1)
        masked_url = f"{proto_user}:****@{suffix}"

print(f"🔌 Attempting connection to: {masked_url}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"ssl": True} if "up.railway.app" not in DATABASE_URL else {} 
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session_maker() as session:
        yield session


async def init_db():
    # Import models here to avoid circular imports
    from app.auth.models import User
    from app.models.history import AssessmentHistory
    from app.models.payment import PaymentRecord
    from app.models.settings import SystemSetting
    from app.models.question import AssessmentQuestion
    from app.models.letter_guidance import LetterGuidance
    from app.models.device_token import UserDeviceToken
    from app.models.notification import NotificationLog

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created/verified successfully.")

    # Seed default questions if table is empty
    await seed_default_questions()
    
    # Seed default letters if table is empty
    await seed_default_letters()


async def seed_default_questions():
    """Seed the database with default psychology & neuroscience questions if none exist."""
    from sqlalchemy import select, func
    from app.models.question import AssessmentQuestion

    async with async_session_maker() as session:
        count = (await session.execute(
            select(func.count(AssessmentQuestion.id))
        )).scalar_one_or_none() or 0

        if count > 0:
            return  # Questions already seeded

        # ── Psychology default questions ──────────────────────────────────
        psychology_questions = [
            {"text": "كيف هو نومك؟", "options": ["مريح ومنتظم", "متقطع أحيانًا", "سيئ أو غير منتظم"]},
            {"text": "إحساسك العام في يومك؟", "options": ["مرتاح ومتوازن", "محتمل", "مستنزف ومتعب"]},
            {"text": "الإحساس المسيطر عليك مؤخرًا؟", "options": ["هدوء واطمئنان", "قلق أو توتر", "حزن أو ثِقل نفسي"]},
            {"text": "قدرتك على الاستمتاع بالأشياء؟", "options": ["طبيعية", "أقل من المعتاد", "شبه معدومة"]},
            {"text": "مستوى القلق أو التفكير الزائد؟", "options": ["قليل", "متوسط", "شديد ومزعج"]},
            {"text": "طاقتك النفسية والجسدية؟", "options": ["جيدة", "متوسطة", "ضعيفة جدًا"]},
            {"text": "نظرتك لنفسك؟", "options": ["إيجابية أو متوازنة", "متذبذبة", "سلبية أو قاسية على نفسي"]},
        ]

        for i, q in enumerate(psychology_questions):
            session.add(AssessmentQuestion(
                assessment_type="psychology",
                order_index=i + 1,
                text=q["text"],
                options=q["options"],
                options_text=None,
                is_active=True,
            ))

        # ── Neuroscience default questions ────────────────────────────────
        neuroscience_questions = [
            {"text": "شدّ العضلات الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "مرتخي في أغلب الجسم", "B": "شدّ متوسط في أكثر من مكان", "C": "شدّ قوي أو تيبّس واضح", "D": "تهدئة ومحاولة استرخاء الآخرين أو النفس"}},
            {"text": "حالة الفك والأسنان الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "الفك مرتخي", "B": "شدّ بسيط", "C": "شدّ قوي أو جزّ", "D": "محاولة تهدئة أو تقليل التوتر"}},
            {"text": "شكل الانتباه البصري الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "نظرة هادئة", "B": "مراقبة نشطة", "C": "تجمّد أو انسحاب بصري", "D": "مراقبة الآخرين لاحتواء الموقف"}},
            {"text": "حالة النبض الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "طبيعي", "B": "أسرع قليلًا", "C": "بطء أو تجمّد", "D": "تغير حسب الآخرين"}},
            {"text": "حالة الهضم الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "هادئ", "B": "انزعاج بسيط", "C": "انزعاج قوي", "D": "تأثر حسب الحالة الاجتماعية"}},
            {"text": "الدافع للحركة الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "حركة حاسمة ومباشرة", "B": "رغبة قوية في الحركة", "C": "انسحاب أو تجمّد", "D": "تهدئة الوضع"}},
            {"text": "مستوى الطاقة الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "طاقة حاسمة", "B": "طاقة عالية", "C": "طاقة منخفضة أو انسحاب", "D": "طاقة موجهة للآخرين"}},
            {"text": "وضوح الذهن الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "تركيز حاسم", "B": "أفكار سريعة", "C": "بطء أو تشوّش", "D": "تركيز على الآخرين"}},
            {"text": "الميل للتواصل الآن؟", "options": ["A", "B", "C", "D"], "options_text": {"A": "مواجهة مباشرة", "B": "تجنب عبر الانشغال", "C": "انسحاب", "D": "تهدئة الآخرين"}},
        ]

        for i, q in enumerate(neuroscience_questions):
            session.add(AssessmentQuestion(
                assessment_type="neuroscience",
                order_index=i + 1,
                text=q["text"],
                options=q["options"],
                options_text=q.get("options_text"),
                is_active=True,
            ))

        await session.commit()
        print("✅ Default assessment questions seeded successfully.")


async def seed_default_letters():
    """Seed the database with default letter guidances if none exist."""
    from sqlalchemy import select, func
    from app.models.letter_guidance import LetterGuidance

    async with async_session_maker() as session:
        count = (await session.execute(
            select(func.count(LetterGuidance.id))
        )).scalar_one_or_none() or 0

        if count > 0:
            return  # Letters already seeded

        spiritual = {
            "ل": "توطيد العلاقة مع الله", "س": "التركيز على التسبيح",
            "ح": "التركيز على التسبيح", "ي": "التركيز على التسبيح",
            "ن": "زيادة الصبر", "م": "زيادة الصوم",
            "ص": "زيادة الصوم", "ط": "زيادة الطهارة"
        }
        
        behavioral = {
            "أ": "زيادة الود واللطف", "ء": "زيادة الود واللطف",
            "ب": "التشافي من الماضي", "ت": "التشافي من الماضي",
            "ج": "السكون والهدوء", "ث": "السكون والهدوء",
            "خ": "السكون والهدوء", "ك": "السكون والهدوء",
            "ع": "تكثيف التعلم", "ر": "تكثيف التعلم",
            "غ": "تكثيف التعلم", "ض": "زيادة التعامل الاجتماعي",
            "ظ": "زيادة التعامل الاجتماعي", "ش": "تقليل الظهور",
            "ز": "تقليل الظهور"
        }
        
        physical = {
            "هـ": "زيادة الرياضة والتنفس", "ه": "زيادة الرياضة والتنفس",
            "و": "زيادة الرياضة والتنفس", "ف": "زيادة الحركة",
            "ق": "زيادة الحركة"
        }

        for letter, text in spiritual.items():
            session.add(LetterGuidance(letter=letter, guidance_type="spiritual", guidance_text=text))
            
        for letter, text in behavioral.items():
            session.add(LetterGuidance(letter=letter, guidance_type="behavioral", guidance_text=text))
            
        for letter, text in physical.items():
            session.add(LetterGuidance(letter=letter, guidance_type="physical", guidance_text=text))

        await session.commit()
        print("✅ Default letter guidances seeded successfully.")
