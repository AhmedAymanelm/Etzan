"""
Firebase Cloud Messaging (FCM) Push Notification Service.

Handles:
- Firebase Admin SDK initialization
- Sending push notifications to individual / multiple devices
- Cleaning up invalid tokens
"""

import os
import json
import base64
import logging
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Firebase state
_firebase_app = None
_firebase_initialized = False


def init_firebase(creds_json: str = None):
    """
    Initialize Firebase Admin SDK using provided credentials, falling back to environment.
    If already initialized, it deletes the current app and re-initializes.
    """
    global _firebase_app, _firebase_initialized

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Clean up existing app if re-initializing
        try:
            app = firebase_admin.get_app()
            firebase_admin.delete_app(app)
        except ValueError:
            pass
            
        _firebase_app = None
        _firebase_initialized = False

        if not creds_json:
            creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
            
        creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

        if creds_json:
            # Decode base64 → JSON dict
            decoded = base64.b64decode(creds_json)
            creds_dict = json.loads(decoded)
            cred = credentials.Certificate(creds_dict)
        elif creds_path:
            cred = credentials.Certificate(creds_path)
        else:
            logger.warning(
                "⚠️  Firebase credentials not configured. "
                "Push notifications will be disabled."
            )
            return

        _firebase_app = firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("✅ Firebase Admin SDK initialized successfully.")

    except Exception as e:
        logger.error(f"❌ Firebase initialization failed: {e}")
        _firebase_initialized = False


async def init_firebase_from_db():
    """Fetch Firebase credentials from the database and initialize."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.settings import SystemSetting
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == 'firebase_credentials_json')
        )
        setting = result.scalar_one_or_none()
        
        if setting and setting.value:
            init_firebase(setting.value)
        else:
            init_firebase() # fallback to env



def is_firebase_ready() -> bool:
    """Check if Firebase SDK is initialized and ready."""
    return _firebase_app is not None


async def send_push_notification(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> Tuple[int, int, List[str]]:
    """
    Send push notification to a list of FCM tokens.

    Returns:
        Tuple of (success_count, failure_count, list_of_invalid_tokens)
    """
    if not is_firebase_ready():
        logger.warning("Firebase not initialized — skipping push notification.")
        return 0, len(tokens), []

    if not tokens:
        return 0, 0, []

    from firebase_admin import messaging

    invalid_tokens = []
    success_count = 0
    failure_count = 0

    # Build the notification
    notification = messaging.Notification(
        title=title,
        body=body,
    )

    # Convert data values to strings (FCM requires string values)
    str_data = None
    if data:
        str_data = {k: str(v) for k, v in data.items()}

    # Send using batch (multicast) for efficiency
    # FCM supports up to 500 tokens per multicast
    batch_size = 500
    for i in range(0, len(tokens), batch_size):
        batch_tokens = tokens[i:i + batch_size]

        message = messaging.MulticastMessage(
            notification=notification,
            data=str_data,
            tokens=batch_tokens,
            # Android-specific config
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="bayt_al_hayat_notifications",
                ),
            ),
            # iOS-specific config
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    ),
                ),
            ),
        )

        try:
            response = messaging.send_each_for_multicast(message)
            success_count += response.success_count
            failure_count += response.failure_count

            # Collect invalid tokens for cleanup
            for idx, send_response in enumerate(response.responses):
                if send_response.exception is not None:
                    error_code = getattr(send_response.exception, 'code', '')
                    # These error codes indicate the token is permanently invalid
                    if error_code in (
                        'NOT_FOUND',
                        'UNREGISTERED',
                        'INVALID_ARGUMENT',
                        'messaging/invalid-registration-token',
                        'messaging/registration-token-not-registered',
                    ):
                        invalid_tokens.append(batch_tokens[idx])

        except Exception as e:
            logger.error(f"FCM batch send error: {e}")
            failure_count += len(batch_tokens)

    logger.info(
        f"📨 Push notification sent: {success_count} success, "
        f"{failure_count} failed, {len(invalid_tokens)} invalid tokens"
    )

    return success_count, failure_count, invalid_tokens


async def send_single_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """Send a push notification to a single device token."""
    success, failed, _ = await send_push_notification([token], title, body, data)
    return success > 0
