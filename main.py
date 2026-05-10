from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routes import psychology_router, neuroscience_router, letter_router, astrology_router, comprehensive_router, history_router, admin_router, payment_router, profile_router, notification_router
from app.auth import auth_router
from app.database import init_db
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup
    await init_db()
    # Initialize Firebase Admin SDK for push notifications
    from app.services.notification_service import init_firebase_from_db
    await init_firebase_from_db()
    yield


# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="Mental Health Assessment API",
    description="API for psychology, neuroscience, letter science, astrology assessments, and comprehensive AI video generation",
    version="1.5.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Rate limit error handler ──────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — allow all for production and mobile clients ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(psychology_router)
app.include_router(neuroscience_router)
app.include_router(letter_router)
app.include_router(astrology_router)
app.include_router(comprehensive_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(payment_router)
app.include_router(notification_router)

# Serve generated media files (audio/video)
os.makedirs("videos", exist_ok=True)
app.mount("/media", StaticFiles(directory="videos"), name="media")


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Mental Health Assessment API with AI Video Generation",
        "version": "1.4.0",
        "endpoints": {
            "psychology": {
                "get_questions": "GET /psychology",
                "submit_answers": "POST /psychology/submit",
                "generate_video": "POST /psychology/generate-video"
            },
            "neuroscience": {
                "get_questions": "GET /neuroscience/questions",
                "submit_answers": "POST /neuroscience/submit"
            },
            "letter": {
                "analyze": "POST /letter/analyze",
                "dictionary": "GET /letter/dictionary"
            },
            "astrology": {
                "analyze": "POST /astrology/analyze",
                "generate_video": "POST /astrology/generate-video"
            },
            "comprehensive": {
                "submit_all": "POST /comprehensive/submit",
                "generate_video": "POST /comprehensive/generate-video"
            },
            "documentation": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# Serve the Admin Dashboard on /admin-ui/
current_dir = os.path.dirname(os.path.abspath(__file__))
dashboard_path = os.path.join(current_dir, "dashboard-admin")
if os.path.exists(dashboard_path):
    app.mount("/admin-ui", StaticFiles(directory=dashboard_path, html=True), name="admin_dashboard")



if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    # Note: reload=True should be used for development, but it may cause issues with __name__ == "__main__" block
    # Actually uvicorn.run("main:app", ...) is better for reload
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
