from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status, BackgroundTasks
from jose import JWTError

from app.auth.email import send_reset_password_email

from app.auth.models import User
from app.auth.schemas import UserRegisterRequest, LoginRequest, ForgetPasswordRequest, ResetPasswordRequest, VerifyResetCodeRequest
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_verification_code,
    decode_token,
)
from datetime import datetime, timedelta


async def register_user(user_data: UserRegisterRequest, background_tasks: BackgroundTasks, db: AsyncSession) -> dict:
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="البريد الإلكتروني مسجل بالفعل"
        )

    # Create new user with hashed password (auto-verified)
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        fullname=user_data.fullname,
        date_of_birth=user_data.date_of_birth,
        city_of_birth=user_data.city_of_birth,
        time_of_birth=user_data.time_of_birth,
        profile_picture_url=user_data.profile_picture_url,
        is_verified=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Automatically generate tokens for the new user so they are logged in immediately
    token_data = {"sub": str(new_user.id), "email": new_user.email}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    return {
        "message": "تم تسجيل المستخدم بنجاح.",
        "user": new_user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def login_user(login_data: LoginRequest, db: AsyncSession) -> dict:
    # Find user by email
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
        )

    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تم إلغاء تنشيط الحساب"
        )

    # Generate tokens
    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


async def forget_password(data: ForgetPasswordRequest, background_tasks: BackgroundTasks, db: AsyncSession) -> dict:
    # Check if email exists
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        # Return same message even if email doesn't exist (security)
        return {
            "message": "إذا كان هذا البريد الإلكتروني مسجلاً، فقد تم إنشاء رمز إعادة تعيين",
            "reset_token": "",
        }

    # Generate 6-digit reset code (15 min expiry)
    reset_code = create_verification_code()
    
    # Save code to user using direct SQL update to avoid StaleDataError
    from sqlalchemy import update
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            verification_code=reset_code,
            verification_code_expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
    )
    await db.commit()

    # Send reset password email in background
    print(f"[DEV] Reset code for {user.email}: {reset_code}")  # للتيست المحلي
    background_tasks.add_task(send_reset_password_email, user.email, reset_code)

    return {
        "message": "إذا كان هذا البريد الإلكتروني مسجلاً، فقد تم إرسال رمز إعادة تعيين كلمة المرور.",
    }


async def verify_reset_code(data: VerifyResetCodeRequest, db: AsyncSession) -> dict:
    # Find user by code
    result = await db.execute(select(User).where(User.verification_code == data.verification_code))
    user = result.scalar_one_or_none()

    if not user:
        return {"is_valid": False, "message": "رمز التحقق غير صحيح"}
        
    # Check if code has expired
    if not user.verification_code_expires_at or user.verification_code_expires_at < datetime.utcnow():
        return {"is_valid": False, "message": "انتهت صلاحية رمز التحقق"}

    return {
        "is_valid": True,
        "message": "الرمز صحيح"
    }


async def reset_password(data: ResetPasswordRequest, db: AsyncSession) -> dict:
    # Find user
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="المستخدم غير موجود"
        )

    # Verify the code
    if user.verification_code != data.verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز التحقق غير صحيح"
        )
        
    # Check if code has expired
    if not user.verification_code_expires_at or user.verification_code_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="انتهت صلاحية رمز التحقق"
        )

    # Update password and clear code
    user.hashed_password = hash_password(data.new_password)
    user.verification_code = None
    user.verification_code_expires_at = None
    await db.commit()

    return {"message": "تم إعادة تعيين كلمة المرور بنجاح"}


async def refresh_token_service(refresh_token: str, db: AsyncSession) -> dict:
    # Decode and validate the refresh token
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز التحديث غير صالح أو منتهي الصلاحية"
        )

    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نوع الرمز غير صالح"
        )

    user_id = payload.get("sub")
    email = payload.get("email")

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="المستخدم غير موجود أو تم إلغاء تنشيط حسابه"
        )

    # Generate new tokens
    token_data = {"sub": str(user.id), "email": user.email}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


async def verify_account(email: str, verification_code: str, db: AsyncSession) -> dict:
    # Find user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="المستخدم غير موجود"
        )

    if user.is_verified:
        return {"message": "الحساب موثق بالفعل"}

    # Check if code matches
    if user.verification_code != verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز التحقق غير صحيح"
        )

    # Check expiration
    expires_at = user.verification_code_expires_at
    if not expires_at or expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="انتهت صلاحية رمز التحقق"
        )

    # Mark user as verified and clear the code
    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None
    await db.commit()

    return {"message": "تم توثيق الحساب بنجاح"}


async def logout() -> dict:
    # With JWT, logout is handled client-side by deleting the tokens
    # In a more advanced setup, we'd blacklist the token
    return {"message": "تم تسجيل الخروج بنجاح. يرجى حذف الرموز الخاصة بك."}
