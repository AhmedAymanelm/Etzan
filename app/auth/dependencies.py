import uuid as _uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String

from app.database import get_db
from app.auth.models import User
from app.auth.utils import decode_token
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login/swagger")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login/swagger", auto_error=False)

async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
        
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
            
        token_type = payload.get("type")
        if token_type != "access":
            return None
            
    except JWTError:
        return None
        
    # Use cast to String for SQLite compatibility (UUID stored as text)
    result = await db.execute(
        select(User).where(cast(User.id, String) == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        return None
        
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="تعذر التحقق من بيانات الاعتماد",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="نوع الرمز غير صالح. يرجى استخدام رمز وصول.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except JWTError:
        raise credentials_exception
        
    # Use cast to String for SQLite compatibility (UUID stored as text)
    result = await db.execute(
        select(User).where(cast(User.id, String) == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="مستخدم غير نشط"
        )
        
    return user
