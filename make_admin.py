import asyncio
import sys
from sqlalchemy import select
from app.database import async_session_maker
from app.auth.models import User

async def main():
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <email>")
        return

    email = sys.argv[1]
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"User with email {email} not found!")
            return
            
        user.is_admin = True
        await db.commit()
        print(f"Success! {email} is now an admin. ✅")

if __name__ == "__main__":
    asyncio.run(main())
