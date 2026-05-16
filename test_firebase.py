import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker
from app.routes.admin import update_firebase_config, FirebaseConfigRequest
from app.auth.models import User

async def test():
    async with async_session_maker() as db:
        admin_user = User(is_admin=True)
        req = FirebaseConfigRequest(credentials_json="e30=") # valid base64 for "{}"
        try:
            res = await update_firebase_config(req, db, admin_user)
            print("Success:", res)
        except Exception as e:
            print("Error:", repr(e))

asyncio.run(test())
