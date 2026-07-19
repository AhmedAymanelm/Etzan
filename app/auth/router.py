from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_db
from app.auth.schemas import (
    UserRegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    ForgetPasswordRequest,
    ForgetPasswordResponse,
    VerifyResetCodeRequest,
    VerifyResetCodeResponse,
    ResetPasswordRequest,
    MessageResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserResponse,
)
from app.auth.service import (
    register_user,
    login_user,
    forget_password,
    verify_reset_code,
    reset_password,
    refresh_token_service,
    logout,
)
from app.auth.dependencies import get_current_user
from app.auth.models import User
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@limiter.limit("10/minute")
async def register(
    request: Request,
    user_data: UserRegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await register_user(user_data, background_tasks, db)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login and get access/refresh tokens",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Standard JSON login endpoint for frontend applications (e.g. Flutter)"""
    return await login_user(login_data, db)


@router.post(
    "/login/swagger",
    summary="OAuth2 Token endpoint for Swagger UI",
    include_in_schema=False,
)
@limiter.limit("5/minute")
async def login_swagger(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    """Dedicated endpoint specifically formatted for Swagger UI OAuth2 requirements"""
    login_req = LoginRequest(email=form_data.username, password=form_data.password)
    response = await login_user(login_req, db)

    return {
        "access_token": response["access_token"],
        "token_type": response["token_type"],
    }


@router.post(
    "/forget-password",
    response_model=ForgetPasswordResponse,
    summary="Request a password reset token",
)
@limiter.limit("3/minute")
async def forget_password_route(
    request: Request,
    data: ForgetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await forget_password(data, background_tasks, db)


@router.post(
    "/verify-reset-code",
    response_model=VerifyResetCodeResponse,
    summary="Verify reset code",
)
@limiter.limit("3/minute")
async def verify_reset_code_route(
    request: Request,
    data: VerifyResetCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    return await verify_reset_code(data, db)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using email and code",
)
@limiter.limit("3/minute")
async def reset_password_route(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    return await reset_password(data, db)


@router.post(
    "/refresh-token",
    response_model=RefreshTokenResponse,
    summary="Get new tokens using refresh token",
)
async def refresh_token_route(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    return await refresh_token_service(data.refresh_token, db)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (client should delete tokens)",
)
async def logout_route():
    return await logout()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile"""
    return current_user


@router.get("/debug-token", include_in_schema=False)
async def debug_token(request: Request, db: AsyncSession = Depends(get_db)):
    """TEMPORARY: Debug JWT token issues - REMOVE AFTER FIXING"""
    import hashlib
    import uuid as _uuid
    from app.auth.utils import SECRET_KEY, ALGORITHM, decode_token
    from jose import jwt, JWTError
    from sqlalchemy import select, text
    from app.auth.models import User
    
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    
    result = {
        "auth_header_present": bool(auth_header),
        "token_length": len(token),
        "secret_key_hash": hashlib.sha256(SECRET_KEY.encode()).hexdigest()[:16] if SECRET_KEY else "NO_KEY",
        "secret_key_length": len(SECRET_KEY) if SECRET_KEY else 0,
    }
    
    if token:
        try:
            payload = decode_token(token)
            result["decode_success"] = True
            user_id = payload.get("sub")
            result["user_id_from_token"] = user_id
            
            # Test 1: Query with UUID object
            try:
                r1 = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
                u1 = r1.scalar_one_or_none()
                result["query_uuid_object"] = u1.email if u1 else "NOT FOUND"
            except Exception as e1:
                result["query_uuid_object"] = f"ERROR: {type(e1).__name__}: {e1}"
            
            # Test 2: Query with string
            try:
                r2 = await db.execute(select(User).where(User.id == user_id))
                u2 = r2.scalar_one_or_none()
                result["query_string"] = u2.email if u2 else "NOT FOUND"
            except Exception as e2:
                result["query_string"] = f"ERROR: {type(e2).__name__}: {e2}"
            
            # Test 3: Raw SQL query
            try:
                r3 = await db.execute(text("SELECT id, email, typeof(id) FROM users WHERE email = :email"), {"email": payload.get("email")})
                row = r3.fetchone()
                if row:
                    result["raw_query"] = {"id": str(row[0]), "email": row[1], "id_type": row[2] if len(row) > 2 else "unknown"}
                    result["id_repr"] = repr(row[0])
                else:
                    result["raw_query"] = "NOT FOUND"
            except Exception as e3:
                result["raw_query"] = f"ERROR: {type(e3).__name__}: {e3}"
            
            # Test 4: Count all users
            try:
                r4 = await db.execute(text("SELECT count(*) FROM users"))
                result["total_users"] = r4.scalar()
            except Exception as e4:
                result["total_users"] = f"ERROR: {e4}"
                
        except JWTError as e:
            result["decode_success"] = False
            result["decode_error"] = str(e)
        except Exception as e:
            result["decode_success"] = False
            result["decode_error"] = f"{type(e).__name__}: {e}"
    
    return result

