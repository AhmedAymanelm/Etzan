from .psychology import router as psychology_router
from .neuroscience import router as neuroscience_router
from .letter import router as letter_router
from .astrology import router as astrology_router
from .comprehensive import router as comprehensive_router
from .history import router as history_router
from .admin import router as admin_router
from .payment import payment_router
from .profile import router as profile_router
from .notification import router as notification_router

__all__ = [
    "psychology_router",
    "neuroscience_router",
    "letter_router",
    "astrology_router",
    "comprehensive_router",
    "history_router",
    "admin_router",
    "payment_router",
    "profile_router",
    "notification_router"
]
