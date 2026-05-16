from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, delete
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.history import AssessmentHistory
from app.models.payment import PaymentRecord
from app.models.settings import SystemSetting

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

# ─── Schemas ───────────────────────────────────────────────────────────────────
class GrantAdminRequest(BaseModel):
    email: EmailStr

class UpdateSettingRequest(BaseModel):
    value: str

class UpdatePricingRequest(BaseModel):
    amount: float
    currency: str = "EGP"

class UpdateGatewayRequest(BaseModel):
    status: Optional[str] = None
    fees: Optional[str] = None
    fees_type: Optional[str] = None
    description: Optional[str] = None
    api_key: Optional[str] = None
    mode: Optional[str] = None

# ─── Admin Guard ───────────────────────────────────────────────────────────────
async def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ─── Overview Stats ────────────────────────────────────────────────────────────

@router.get("/stats", summary="Get dashboard key metrics")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one_or_none() or 0
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar_one_or_none() or 0
    total_assessments = (await db.execute(select(func.count(AssessmentHistory.id)))).scalar_one_or_none() or 0

    
    # Calculate Total Revenue (only SUCCESS payments)
    total_revenue = (await db.execute(
        select(func.sum(PaymentRecord.amount)).where(PaymentRecord.status == "SUCCESS")
    )).scalar_one_or_none() or 0.0
    
    # Breakdown of Users by Age Demographic (for Pie Chart)
    users_dob_result = await db.execute(select(User.date_of_birth).where(User.date_of_birth.isnot(None)))
    dobs = users_dob_result.scalars().all()
    
    age_groups = {"Under 25": 0, "25-34": 0, "35-44": 0, "45+": 0}
    today = datetime.utcnow().date()
    for dob in dobs:
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 25: age_groups["Under 25"] += 1
        elif age < 35: age_groups["25-34"] += 1
        elif age < 45: age_groups["35-44"] += 1
        else: age_groups["45+"] += 1
        
    breakdown = {k: v for k, v in age_groups.items() if v > 0}
    if not breakdown:
        breakdown = {"No Data Yet": 1}

    # Journey Completion Rate (Drop-off Analysis)
    users_with_assessments_result = await db.execute(
        select(AssessmentHistory.user_id, AssessmentHistory.assessment_type)
        .order_by(AssessmentHistory.user_id, AssessmentHistory.created_at)
    )
    all_assessments = users_with_assessments_result.all()

    # Journey Completion Rate (Unique users per stage, non-sequential)
    user_journey = {}
    for user_id, assessment_type in all_assessments:
        if user_id not in user_journey:
            user_journey[user_id] = set()
        # Clean type name (lower case and strip)
        ptype = assessment_type.lower().strip()
        user_journey[user_id].add(ptype)

    journey_stages = {
        "Only Psychology": 0,
        "Psychology + Neuroscience": 0,
        "Psychology + Neuro + Letter": 0,
        "Psychology + Neuro + Letter + Astrology": 0,
        "Fully Completed": 0
    }

    # REVISED FUNNEL: Count cumulative users reaching each stage in the defined path
    # Even if they skip psychology, if they reached astrology, we often count them reaching that far
    # but the previous buckets were misleadingly mutually exclusive.
    # Let's count EXACTLY how many unique users have done EACH stage.
    unique_stage_counts = {
        "psychology": 0,
        "neuroscience": 0,
        "letter": 0,
        "astrology": 0,
        "comprehensive": 0
    }
    for completed_types in user_journey.values():
        for s in unique_stage_counts.keys():
            if s in completed_types:
                unique_stage_counts[s] += 1

    unique_stage_counts = {
        "psychology": 0,
        "neuroscience": 0,
        "letter": 0,
        "astrology": 0,
        "comprehensive": 0
    }
    
    for completed_types in user_journey.values():
        for db_type in unique_stage_counts.keys():
            if db_type in completed_types:
                unique_stage_counts[db_type] += 1

    # Return the direct counts. 
    # NOTE: The frontend (app.js) was doing a cumulative sum, which we will now disable 
    # to show absolute unique user counts per stage. 
    # For now, we will use a specific key "absolute_counts" to signify this.
    
    # New users in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_users_30d = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
    )).scalar_one_or_none() or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_assessments": total_assessments,

        "new_users_30d": new_users_30d,
        "total_revenue": total_revenue,
        "breakdown": breakdown,
        "journey": unique_stage_counts,
        "is_absolute": True # Flag for frontend
    }


@router.get("/users/growth", summary="Daily user registration counts (last 14 days)")
async def get_user_growth(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Returns daily registration count for the last 14 days."""
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    # Truncate to date to group by day
    result = await db.execute(
        select(
            func.date(User.created_at).label("day"),
            func.count(User.id).label("count")
        )
        .where(User.created_at >= fourteen_days_ago)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )
    rows = result.all()

    # Create a map of existing data
    data_map = {row.day: row.count for row in rows}
    
    # Fill in all 14 days, even if 0 registrations
    data = []
    for i in range(14, -1, -1):
        target_date = (datetime.utcnow() - timedelta(days=i)).date()
        count = data_map.get(target_date, 0)
        data.append({
            "month": target_date.strftime("%b %d"), # Keeping key as 'month' so frontend JS doesn't break
            "count": count
        })

    return data


# ─── User Management ───────────────────────────────────────────────────────────

@router.get("/users", summary="Get list of all users")
async def get_users(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    from app.models.subscription import UserSubscription
    
    result = await db.execute(select(User).order_by(User.created_at.desc()).offset(skip).limit(limit))
    users = result.scalars().all()

    # For each user, count their assessments
    user_ids = [u.id for u in users]
    counts_result = await db.execute(
        select(AssessmentHistory.user_id, func.count(AssessmentHistory.id))
        .where(AssessmentHistory.user_id.in_(user_ids))
        .group_by(AssessmentHistory.user_id)
    )
    counts_map = {str(row[0]): row[1] for row in counts_result.all()}
    
    # Get active subscriptions
    now = datetime.utcnow()
    subs_result = await db.execute(
        select(UserSubscription.user_id)
        .where(
            UserSubscription.user_id.in_(user_ids),
            UserSubscription.is_active == True,
            UserSubscription.expires_at > now
        )
    )
    active_sub_users = {str(uid) for uid in subs_result.scalars().all()}

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "fullname": u.fullname,
            "date_of_birth": str(u.date_of_birth) if u.date_of_birth else None,
            "place_of_birth": u.city_of_birth,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "profile_picture_url": u.profile_picture_url,
            "created_at": u.created_at,
            "assessment_count": counts_map.get(str(u.id), 0),
            "free_trial_used": u.free_trial_used,
            "has_active_subscription": str(u.id) in active_sub_users
        }
        for u in users
    ]


@router.get("/users/{user_id}/details", summary="Get single user details + their assessments")
async def get_user_details(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    assessments_result = await db.execute(
        select(AssessmentHistory)
        .where(AssessmentHistory.user_id == user_id)
        .order_by(AssessmentHistory.created_at.desc())
    )
    assessments = assessments_result.scalars().all()

    return {
        "id": str(user.id),
        "email": user.email,
        "fullname": user.fullname,
        "date_of_birth": str(user.date_of_birth) if user.date_of_birth else None,
        "place_of_birth": user.city_of_birth,
        "time_of_birth": str(user.time_of_birth) if user.time_of_birth else None,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "profile_picture_url": user.profile_picture_url,
        "created_at": user.created_at,
        "assessments": [
            {
                "id": str(a.id),
                "type": a.assessment_type,

                "created_at": a.created_at,
            }
            for a in assessments
        ]
    }


@router.post("/users/{user_id}/toggle-status", summary="Toggle user active status")
async def toggle_user_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    await db.commit()
    return {"message": f"User is now {'Active' if user.is_active else 'Inactive'}", "is_active": user.is_active}


@router.delete("/users/{user_id}", summary="Delete a user and all their data")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"message": "User deleted successfully"}


# ─── Assessment Management ─────────────────────────────────────────────────────

JOURNEY_STAGES = ["psychology", "neuroscience", "letter", "astrology", "comprehensive"]

@router.get("/assessments/journey", summary="Get user journey progress for all users")
async def get_user_journeys(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    # Get all users who have at least one assessment, ordered by their LATEST assessment date
    users_result = await db.execute(
        select(User)
        .join(AssessmentHistory, AssessmentHistory.user_id == User.id)
        .group_by(User.id)
        .order_by(func.max(AssessmentHistory.created_at).desc())
    )
    users = users_result.scalars().all()

    # For each user, get their set of completed assessment types
    user_ids = [u.id for u in users]
    assessments_result = await db.execute(
        select(
            AssessmentHistory.user_id,
            AssessmentHistory.assessment_type,

            AssessmentHistory.created_at
        )
        .where(AssessmentHistory.user_id.in_(user_ids))
        .order_by(AssessmentHistory.created_at)
    )
    all_assessments = assessments_result.all()

    # Build per-user data
    user_data = {str(u.id): {
        "id": str(u.id),
        "name": u.fullname,
        "email": u.email,
        "completed_stages": set(),

        "last_activity": None
    } for u in users}

    for row in all_assessments:
        uid = str(row.user_id)
        if uid in user_data:
            # Normalize assessment type
            clean_type = row.assessment_type.lower().strip()
            user_data[uid]["completed_stages"].add(clean_type)

            if not user_data[uid]["last_activity"] or row.created_at > user_data[uid]["last_activity"]:
                user_data[uid]["last_activity"] = row.created_at

    # Format output
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "email": d["email"],

            "last_activity": d["last_activity"].isoformat() if d["last_activity"] else None,
            "stages": {
                stage: (stage in d["completed_stages"])
                for stage in JOURNEY_STAGES
            },
            "completed_count": len(d["completed_stages"]),
            "total_stages": len(JOURNEY_STAGES)
        }
        for d in user_data.values()
    ]


@router.get("/assessments", summary="Get all assessments")
async def get_assessments(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(
        select(AssessmentHistory, User.email.label("user_email"), User.fullname)
        .join(User, AssessmentHistory.user_id == User.id)
        .order_by(AssessmentHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.all()

    return [
        {
            "id": str(item.AssessmentHistory.id),
            "user_id": str(item.AssessmentHistory.user_id),
            "user_email": item.user_email,
            "user_name": item.fullname,
            "type": item.AssessmentHistory.assessment_type,

            "created_at": item.AssessmentHistory.created_at
        }
        for item in items
    ]


@router.get("/assessments/{assessment_id}/result", summary="Get full result data of an assessment")
async def get_assessment_result(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(
        select(AssessmentHistory, User.email.label("user_email"), User.fullname)
        .join(User, AssessmentHistory.user_id == User.id)
        .where(AssessmentHistory.id == assessment_id)
    )
    item = result.first()
    if not item:
        raise HTTPException(status_code=404, detail="Assessment not found")

    return {
        "id": str(item.AssessmentHistory.id),
        "user_email": item.user_email,
        "user_name": item.fullname,
        "type": item.AssessmentHistory.assessment_type,
        "input_data": item.AssessmentHistory.input_data,
        "result_data": item.AssessmentHistory.result_data,

        "created_at": item.AssessmentHistory.created_at
    }


@router.delete("/assessments/{assessment_id}", summary="Delete an assessment record")
async def delete_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(AssessmentHistory).where(AssessmentHistory.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    await db.delete(assessment)
    await db.commit()
    return {"message": "Assessment deleted successfully"}


# ─── Payment Management (Admin) ────────────────────────────────────────────────

@router.get("/payments", summary="Get all payment records")
async def get_admin_payments(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(
        select(PaymentRecord, User.email.label("user_email"), User.fullname)
        .join(User, PaymentRecord.user_id == User.id)
        .order_by(PaymentRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.all()

    return [
        {
            "id": str(item.PaymentRecord.id),
            "user_id": str(item.PaymentRecord.user_id),
            "user_email": item.user_email,
            "user_name": item.fullname,
            "order_id": item.PaymentRecord.order_id,
            "session_id": item.PaymentRecord.session_id,
            "service_type": item.PaymentRecord.service_type,
            "amount": item.PaymentRecord.amount,
            "currency": item.PaymentRecord.currency,
            "status": item.PaymentRecord.status,
            "payment_method": item.PaymentRecord.payment_method,
            "created_at": item.PaymentRecord.created_at
        }
        for item in items
    ]


# ─── System Health ─────────────────────────────────────────────────────────────

@router.get("/health", summary="System health and API key status")
async def get_system_health(
    admin: User = Depends(get_admin_user)
):
    import os

    keys_to_check = [
        ("OPENAI_API_KEY", "OpenAI"),
        ("DATABASE_URL", "Database"),
        ("SECRET_KEY", "JWT Secret"),
        ("CLOUDINARY_CLOUD_NAME", "Cloudinary"),
        ("ASTROLOGY_API_KEY", "Astrology API"),
        ("OPENAI_MODEL", "OpenAI Model")
    ]

    health_status = {}
    all_ok = True
    for env_key, label in keys_to_check:
        val = os.getenv(env_key)
        configured = bool(val and len(val) > 3)
        if not configured:
            all_ok = False
        health_status[label] = {
            "configured": configured,
            "status": "✓ Active" if configured else "✗ Missing"
        }

    return {
        "overall": "healthy" if all_ok else "degraded",
        "services": health_status,
        "platform": "Bayt Al Hayat (بيت الحياة) Admin Engine",
        "checked_at": datetime.utcnow().isoformat()
    }

# ─── Pattern Music Management ──────────────────────────────────────────────────

from app.utils.cloudinary_upload import upload_audio_to_cloudinary

@router.get("/settings/neuro-music", summary="Get current music URLs for neural patterns")
async def get_neuro_music_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Retrieve all stored Cloudinary background music URLs for patterns."""
    keys = ["neuro_music_fight", "neuro_music_flight", "neuro_music_freeze", "neuro_music_fawn"]
    result = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(keys)))
    settings = result.scalars().all()
    
    settings_dict = {s.key: s.value for s in settings}
    return [
        {"pattern": "Fight", "urls": [u.strip() for u in settings_dict.get("neuro_music_fight", "").split(",") if u.strip()]},
        {"pattern": "Flight", "urls": [u.strip() for u in settings_dict.get("neuro_music_flight", "").split(",") if u.strip()]},
        {"pattern": "Freeze", "urls": [u.strip() for u in settings_dict.get("neuro_music_freeze", "").split(",") if u.strip()]},
        {"pattern": "Fawn", "urls": [u.strip() for u in settings_dict.get("neuro_music_fawn", "").split(",") if u.strip()]},
    ]


@router.post("/settings/neuro-music/upload", summary="Upload music for a neural pattern")
async def upload_neuro_music(
    pattern: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Uploads an audio file to Cloudinary and saves URL in settings"""
    if pattern not in ["Fight", "Flight", "Freeze", "Fawn"]:
        raise HTTPException(status_code=400, detail="Invalid pattern name")
        
    if not file.content_type.startswith("audio/") and not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be an audio file.")
        
    try:
        # Upload to Cloudinary
        secure_url = await upload_audio_to_cloudinary(file, folder="neuro_patterns_music")
        
        # Save to DB
        setting_key = f"neuro_music_{pattern.lower()}"
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == setting_key))
        setting = result.scalar_one_or_none()
        
        if setting:
            # Append if not empty, otherwise set
            current_values = [v.strip() for v in setting.value.split(",") if v.strip()]
            if secure_url not in current_values:
                current_values.append(secure_url)
            setting.value = ",".join(current_values)
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSetting(
                key=setting_key,
                value=secure_url,
                group="multimedia",
                label=f"Neuro Science Music: {pattern}",
                description=f"Background music URL for {pattern} pattern",
                is_secret=False
            )
            db.add(setting)
            
        await db.commit()
        return {"message": f"Successfully uploaded music for {pattern}", "url": secure_url}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/settings/neuro-music/{pattern}", summary="Delete music for a neural pattern")
async def delete_neuro_music(
    pattern: str,
    url: str = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if pattern not in ["Fight", "Flight", "Freeze", "Fawn"]:
        raise HTTPException(status_code=400, detail="Invalid pattern name")
        
    setting_key = f"neuro_music_{pattern.lower()}"
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == setting_key))
    setting = result.scalar_one_or_none()
    
    if setting:
        if url:
            # Delete specific URL
            current_values = [v.strip() for v in setting.value.split(",") if v.strip()]
            if url in current_values:
                current_values.remove(url)
            setting.value = ",".join(current_values)
        else:
            # Delete all
            setting.value = ""
            
        setting.updated_at = datetime.utcnow()
        await db.commit()
        
    return {"message": f"Successfully updated music list for {pattern}"}

# ─── Admin User Management ─────────────────────────────────────────────────────

@router.get("/admins", summary="List all admin users")
async def list_admins(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(
        select(User).where(User.is_admin == True)
    )
    admins = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.fullname,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in admins
    ]


@router.post("/admins/grant", summary="Grant admin access to a user by email")
async def grant_admin(
    body: GrantAdminRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found with that email")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="User is already an admin")
    user.is_admin = True
    await db.commit()
    return {"message": f"✅ {user.fullname} ({user.email}) is now an admin"}


@router.delete("/admins/revoke/{user_id}", summary="Revoke admin access from a user")
async def revoke_admin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=400, detail="Cannot revoke your own admin access")
    user.is_admin = False
    await db.commit()
    return {"message": f"❌ Admin access revoked for {user.fullname} ({user.email})"}


# ─── Settings: Pricing ────────────────────────────────────────────────────────
@router.get("/settings/pricing", summary="List pricing settings")
async def get_pricing_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    # Services we currently offer
    services = [
        "monthly_subscription"
    ]
    
    # We query both price_* and currency_* keys
    keys_to_fetch = [f"price_{s}" for s in services] + [f"currency_{s}" for s in services]
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(keys_to_fetch))
    )
    rows = {r.key: r.value for r in result.scalars().all()}
    
    return [
        {
            "service_type": service,
            "amount": float(rows.get(f"price_{service}", "250.00")),  # Default Fallback
            "currency": rows.get(f"currency_{service}", "EGP")       # Default Currency Fallback
        }
        for service in services
    ]

@router.put("/settings/pricing/{service_id}", summary="Update a price setting")
async def update_pricing_setting(
    service_id: str,
    body: UpdatePricingRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    from datetime import datetime
    try:
        new_price = float(body.amount)
        if new_price < 0:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid price amount. Must be a positive number.")

    price_key = f"price_{service_id}"
    currency_key = f"currency_{service_id}"
    
    # Save Price Amount
    result_price = await db.execute(select(SystemSetting).where(SystemSetting.key == price_key))
    setting_price = result_price.scalar_one_or_none()
    
    if not setting_price:
        setting_price = SystemSetting(
            key=price_key,
            value=f"{new_price:.2f}",
            group="pricing",
            label=f"Price For: {service_id.replace('_', ' ').title()}",
            description="Base price users pay for this service",
            is_secret=False
        )
        db.add(setting_price)
    else:
        setting_price.value = f"{new_price:.2f}"
        setting_price.updated_at = datetime.utcnow()

    # Save Currency
    new_currency = body.currency.strip().upper() or "EGP"
    result_curr = await db.execute(select(SystemSetting).where(SystemSetting.key == currency_key))
    setting_curr = result_curr.scalar_one_or_none()
    
    if not setting_curr:
        setting_curr = SystemSetting(
            key=currency_key,
            value=new_currency,
            group="pricing",
            label=f"Currency For: {service_id.replace('_', ' ').title()}",
            description="Currency used for this service price",
            is_secret=False
        )
        db.add(setting_curr)
    else:
        setting_curr.value = new_currency
        setting_curr.updated_at = datetime.utcnow()

    await db.commit()
    return {"message": f"✅ Pricing for {service_id.replace('_', ' ').title()} updated to {new_price:.2f} {new_currency}"}

# ─── Settings: AI Models ────────────────────────────────────────────────────────

def _mask(value: str, is_secret: bool) -> str:
    """Return masked value for secret keys, showing only first 8 chars."""
    if not is_secret or not value:
        return value or ""
    visible = value[:8]
    return visible + "•" * min(20, max(4, len(value) - 8))


@router.get("/settings/models", summary="List AI model settings")
async def get_model_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.group == "ai_models").order_by(SystemSetting.key)
    )
    rows = result.scalars().all()

    # Fallback to env for keys missing from DB
    import os
    return [
        {
            "key": r.key,
            "label": r.label,
            "description": r.description,
            "is_secret": r.is_secret,
            "value": _mask(r.value or os.getenv(r.key.upper(), ""), r.is_secret),
            "has_value": bool(r.value),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.put("/settings/models/{key}", summary="Update an AI model setting")
async def update_model_setting(
    key: str,
    body: UpdateSettingRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    from datetime import datetime
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key, SystemSetting.group == "ai_models")
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    setting.value = body.value
    setting.updated_at = datetime.utcnow()
    await db.commit()
    return {"message": f"✅ '{setting.label}' updated successfully"}


@router.post("/settings/models/{key}/test", summary="Test an AI model connection")
async def test_model_setting(
    key: str,
    body: UpdateSettingRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    import httpx
    val = body.value.strip()

    try:
        if key == "openai_api_key":
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {val}"})
                res.raise_for_status()
            return {"message": "OpenAI connection successful"}

        elif key == "astrology_api_key":
            payload = {
                "year": 2000, "month": 1, "date": 1,
                "hours": 12, "minutes": 0, "seconds": 0,
                "latitude": 30.0, "longitude": 31.0, "timezone": 2.0,
                "config": {"observation_point": "topocentric", "ayanamsha": "tropical", "language": "en"}
            }
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post("https://json.freeastrologyapi.com/western/planets", headers={"x-api-key": val}, json=payload)
                res.raise_for_status()
            return {"message": "Astrology API connection successful"}

        elif "key" in key or "secret" in key:
            if len(val) > 8:
                return {"message": f"Format OK (length: {len(val)}). Full automated test not available for this key."}
            else:
                raise HTTPException(status_code=400, detail="Key seems too short to be valid")

        return {"message": "Value looks OK"}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"API rejected the key (Status {e.response.status_code})")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error testing key: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@router.get("/settings/models/balances", summary="Get remaining balance/tokens for AI models")
async def get_ai_models_balances(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    import httpx
    import os
    import base64
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.group == "ai_models")
    )
    rows = result.scalars().all()
    settings_dict = {r.key: r.value or os.getenv(r.key.upper(), "") for r in rows}

    balances = []

    def add_bal(service, balance, status):
        balances.append({"service": service, "balance": balance, "status": status})

    # OpenAI
    openai_key = settings_dict.get("openai_api_key")
    if openai_key:
        add_bal("OpenAI", "Check Dashboard", "warning")
    else:
        add_bal("OpenAI", "Not Configured", "error")


    # Astrology API
    astro_key = settings_dict.get("astrology_api_key")
    if astro_key:
        add_bal("Astrology API", "Active (Free Tier)", "ok")
    else:
        add_bal("Astrology API", "Not Configured", "error")

    # Cloudinary
    cloud_name = settings_dict.get("cloudinary_cloud_name")
    cloud_key = settings_dict.get("cloudinary_api_key")
    cloud_secret = settings_dict.get("cloudinary_api_secret")
    if cloud_name and cloud_key and cloud_secret:
        try:
            auth_header = f"Basic {base64.b64encode(f'{cloud_key}:{cloud_secret}'.encode()).decode()}"
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get(f"https://api.cloudinary.com/v1_1/{cloud_name}/usage", headers={"Authorization": auth_header})
                if res.status_code == 200:
                    data = res.json()
                    credits_usage = data.get("credits", {}).get("usage", 0)
                    credits_limit = data.get("credits", {}).get("limit", 0)
                    if credits_limit:
                        pct = round((credits_usage / credits_limit) * 100, 1)
                        add_bal("Cloudinary", f"{pct}% Used", "ok" if pct < 90 else "warning")
                    else:
                        add_bal("Cloudinary", f"{credits_usage} utilized", "ok")
                else:
                    add_bal("Cloudinary", "Check Dashboard", "warning")
        except Exception:
            add_bal("Cloudinary", "Connection Failed", "error")
    else:
        add_bal("Cloudinary", "Not Fully Configured", "error")

    return balances



# ─── Settings: Payment Gateways ────────────────────────────────────────────────

@router.get("/settings/gateways", summary="List payment gateways")
async def get_gateway_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.group == "payment_gateway")
    )
    rows = result.scalars().all()
    data = {r.key: r for r in rows}

    def gv(k):
        """Get gateway value, masked if secret."""
        r = data.get(k)
        if not r:
            return ""
        return _mask(r.value or "", r.is_secret)

    return [
        {
            "id": "fawaterk",
            "name": "Fawaterk",
            "status": data.get("fawaterk_status", type("o", (), {"value": "inactive"})()).value,
            "fees": gv("fawaterk_fees"),
            "fees_type": gv("fawaterk_fees_type"),
            "description": gv("fawaterk_description"),
            "api_key": gv("fawaterk_api_key"),
            "mode": gv("fawaterk_mode"),
        }
    ]


@router.put("/settings/gateways/fawaterk", summary="Update Fawaterk gateway settings")
async def update_fawaterk_settings(
    body: UpdateGatewayRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    from datetime import datetime

    field_map = {
        "status": "fawaterk_status",
        "fees": "fawaterk_fees",
        "fees_type": "fawaterk_fees_type",
        "description": "fawaterk_description",
        "api_key": "fawaterk_api_key",
        "mode": "fawaterk_mode",
    }

    updated = []
    for field, db_key in field_map.items():
        val = getattr(body, field)
        if val is not None:
            result = await db.execute(select(SystemSetting).where(SystemSetting.key == db_key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = val
                setting.updated_at = datetime.utcnow()
                updated.append(db_key)
            else:
                setting = SystemSetting(
                    key=db_key,
                    value=val,
                    group="payment_gateway",
                    label=db_key.replace('_', ' ').title(),
                    is_secret="key" in db_key
                )
                db.add(setting)
                updated.append(db_key)

    await db.commit()
    return {"message": f"✅ Fawaterk gateway updated ({len(updated)} fields)"}


# ─── Questions Management (CRUD) ──────────────────────────────────────────────

from app.models.question import AssessmentQuestion

class CreateQuestionRequest(BaseModel):
    text: str
    options: Any  # list for psychology, list for neuroscience
    options_text: Optional[Dict[str, str]] = None  # only for neuroscience
    is_active: bool = True

class UpdateQuestionRequest(BaseModel):
    text: Optional[str] = None
    options: Optional[Any] = None
    options_text: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

class ReorderQuestionsRequest(BaseModel):
    order: List[int]  # list of question IDs in desired order


@router.get("/questions/{assessment_type}", summary="Get all questions for an assessment type")
async def get_questions(
    assessment_type: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Get all questions for a given assessment type (psychology / neuroscience)."""
    if assessment_type not in ("psychology", "neuroscience"):
        raise HTTPException(status_code=400, detail="Type must be 'psychology' or 'neuroscience'")

    result = await db.execute(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.assessment_type == assessment_type)
        .order_by(AssessmentQuestion.order_index)
    )
    questions = result.scalars().all()
    return [q.to_dict() for q in questions]


@router.post("/questions/{assessment_type}", summary="Add a new question")
async def create_question(
    assessment_type: str,
    body: CreateQuestionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Add a new question to an assessment type."""
    if assessment_type not in ("psychology", "neuroscience"):
        raise HTTPException(status_code=400, detail="Type must be 'psychology' or 'neuroscience'")

    # Get the next order_index
    max_order = (await db.execute(
        select(func.max(AssessmentQuestion.order_index))
        .where(AssessmentQuestion.assessment_type == assessment_type)
    )).scalar_one_or_none() or 0

    question = AssessmentQuestion(
        assessment_type=assessment_type,
        order_index=max_order + 1,
        text=body.text,
        options=body.options,
        options_text=body.options_text,
        is_active=body.is_active,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return {"message": "✅ Question added successfully", "question": question.to_dict()}


@router.put("/questions/{question_id}", summary="Update a question")
async def update_question(
    question_id: int,
    body: UpdateQuestionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update an existing question."""
    result = await db.execute(
        select(AssessmentQuestion).where(AssessmentQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if body.text is not None:
        question.text = body.text
    if body.options is not None:
        question.options = body.options
    if body.options_text is not None:
        question.options_text = body.options_text
    if body.is_active is not None:
        question.is_active = body.is_active

    question.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(question)
    return {"message": "✅ Question updated successfully", "question": question.to_dict()}


@router.delete("/questions/{question_id}", summary="Delete a question")
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete a question permanently."""
    result = await db.execute(
        select(AssessmentQuestion).where(AssessmentQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    assessment_type = question.assessment_type
    deleted_order = question.order_index

    await db.delete(question)

    # Re-index remaining questions
    remaining = (await db.execute(
        select(AssessmentQuestion)
        .where(
            AssessmentQuestion.assessment_type == assessment_type,
            AssessmentQuestion.order_index > deleted_order
        )
        .order_by(AssessmentQuestion.order_index)
    )).scalars().all()

    for q in remaining:
        q.order_index -= 1

    await db.commit()
    return {"message": "✅ Question deleted successfully"}


@router.put("/questions/reorder/{assessment_type}", summary="Reorder questions")
async def reorder_questions(
    assessment_type: str,
    body: ReorderQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Reorder questions by providing a list of question IDs in the desired order."""
    if assessment_type not in ("psychology", "neuroscience"):
        raise HTTPException(status_code=400, detail="Type must be 'psychology' or 'neuroscience'")

    for new_index, question_id in enumerate(body.order, start=1):
        result = await db.execute(
            select(AssessmentQuestion).where(
                AssessmentQuestion.id == question_id,
                AssessmentQuestion.assessment_type == assessment_type
            )
        )
        question = result.scalar_one_or_none()
        if question:
            question.order_index = new_index

    await db.commit()
    return {"message": f"✅ {assessment_type} questions reordered successfully"}


# ─── Subscription Management (Admin) ──────────────────────────────────────────

from app.models.subscription import UserSubscription


@router.get("/subscriptions", summary="Get all user subscriptions")
async def get_all_subscriptions(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """List all subscriptions with user info, sorted by newest first."""
    result = await db.execute(
        select(UserSubscription, User.email.label("user_email"), User.fullname)
        .join(User, UserSubscription.user_id == User.id)
        .order_by(UserSubscription.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.all()
    now = datetime.utcnow()

    return [
        {
            "id": str(item.UserSubscription.id),
            "user_id": str(item.UserSubscription.user_id),
            "user_email": item.user_email,
            "user_name": item.fullname,
            "plan_type": item.UserSubscription.plan_type,
            "is_active": item.UserSubscription.is_active,
            "granted_by_admin": item.UserSubscription.granted_by_admin,
            "started_at": item.UserSubscription.started_at.isoformat() if item.UserSubscription.started_at else None,
            "expires_at": item.UserSubscription.expires_at.isoformat() if item.UserSubscription.expires_at else None,
            "days_remaining": max(0, (item.UserSubscription.expires_at - now).days) if item.UserSubscription.expires_at else 0,
            "is_expired": item.UserSubscription.expires_at < now if item.UserSubscription.expires_at else True,
            "payment_record_id": str(item.UserSubscription.payment_record_id) if item.UserSubscription.payment_record_id else None,
            "created_at": item.UserSubscription.created_at.isoformat() if item.UserSubscription.created_at else None,
        }
        for item in items
    ]


@router.post("/users/{user_id}/grant-subscription", summary="Grant a free 30-day subscription")
async def grant_subscription(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Admin manually grants a 30-day subscription without requiring payment."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    sub = UserSubscription(
        user_id=user.id,
        payment_record_id=None,
        started_at=now,
        expires_at=now + timedelta(days=30),
        is_active=True,
        plan_type="admin_grant",
        granted_by_admin=True,
    )
    db.add(sub)
    await db.commit()

    return {
        "message": f"✅ Subscription granted to {user.fullname} ({user.email}) — expires in 30 days",
        "expires_at": sub.expires_at.isoformat()
    }


@router.post("/users/{user_id}/revoke-subscription", summary="Revoke all active subscriptions for a user")
async def revoke_subscription(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Marks all active subscriptions for a user as inactive immediately."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subs_result = await db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.is_active == True,
        )
    )
    subs = subs_result.scalars().all()

    if not subs:
        raise HTTPException(status_code=404, detail="No active subscriptions found for this user")

    for sub in subs:
        sub.is_active = False
        sub.expires_at = datetime.utcnow()

    await db.commit()
    return {"message": f"❌ All active subscriptions revoked for {user.fullname} ({user.email})"}


@router.post("/users/{user_id}/reset-free-trial", summary="Reset the free trial for a user")
async def reset_free_trial(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Resets free_trial_used so the user gets another free analysis attempt."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.free_trial_used = False
    await db.commit()
    return {"message": f"✅ Free trial reset for {user.fullname} ({user.email})"}


@router.get("/subscriptions/stats", summary="Get subscription statistics")
async def get_subscription_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Returns aggregate subscription metrics for the admin dashboard."""
    from sqlalchemy import func
    now = datetime.utcnow()

    total_active = (await db.execute(
        select(func.count(UserSubscription.id)).where(
            UserSubscription.is_active == True,
            UserSubscription.expires_at > now,
        )
    )).scalar_one_or_none() or 0

    total_ever = (await db.execute(
        select(func.count(UserSubscription.id))
    )).scalar_one_or_none() or 0

    admin_granted = (await db.execute(
        select(func.count(UserSubscription.id)).where(
            UserSubscription.granted_by_admin == True,
            UserSubscription.is_active == True,
            UserSubscription.expires_at > now,
        )
    )).scalar_one_or_none() or 0

    trials_used = (await db.execute(
        select(func.count(User.id)).where(User.free_trial_used == True)
    )).scalar_one_or_none() or 0

    return {
        "total_active_subscriptions": total_active,
        "total_subscriptions_ever": total_ever,
        "admin_granted_active": admin_granted,
        "paid_active": total_active - admin_granted,
        "users_with_trial_used": trials_used,
    }


# ─── Push Notifications Management (Admin) ─────────────────────────────────────

from app.models.device_token import UserDeviceToken
from app.models.notification import NotificationLog
from app.services.notification_service import send_push_notification, is_firebase_ready


class SendNotificationRequest(BaseModel):
    title: str
    body: str
    target_type: str = "broadcast"  # "broadcast" | "user" | "group"
    target_user_ids: Optional[List[str]] = None  # Required for "user" and "group"
    data_payload: Optional[Dict[str, Any]] = None  # Extra data (e.g. deeplink)


@router.get("/notifications/stats", summary="Get notification system statistics")
async def get_notification_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Returns stats about registered devices, total notifications sent, etc."""
    # Total registered active devices
    total_devices = (await db.execute(
        select(func.count(UserDeviceToken.id)).where(UserDeviceToken.is_active == True)
    )).scalar_one_or_none() or 0

    # Devices by platform
    android_devices = (await db.execute(
        select(func.count(UserDeviceToken.id)).where(
            UserDeviceToken.is_active == True,
            UserDeviceToken.device_type == "android"
        )
    )).scalar_one_or_none() or 0

    ios_devices = (await db.execute(
        select(func.count(UserDeviceToken.id)).where(
            UserDeviceToken.is_active == True,
            UserDeviceToken.device_type == "ios"
        )
    )).scalar_one_or_none() or 0

    # Unique users with devices
    unique_users = (await db.execute(
        select(func.count(func.distinct(UserDeviceToken.user_id))).where(
            UserDeviceToken.is_active == True
        )
    )).scalar_one_or_none() or 0

    # Total notifications sent
    total_notifications = (await db.execute(
        select(func.count(NotificationLog.id))
    )).scalar_one_or_none() or 0

    # Total successfully delivered
    total_delivered = (await db.execute(
        select(func.sum(NotificationLog.sent_count))
    )).scalar_one_or_none() or 0

    # Last notification
    last_notif = (await db.execute(
        select(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    return {
        "total_devices": total_devices,
        "android_devices": android_devices,
        "ios_devices": ios_devices,
        "unique_users_with_devices": unique_users,
        "total_notifications_sent": total_notifications,
        "total_delivered": total_delivered,
        "firebase_ready": is_firebase_ready(),
        "last_notification": {
            "title": last_notif.title,
            "created_at": last_notif.created_at.isoformat(),
        } if last_notif else None,
    }


class FirebaseConfigRequest(BaseModel):
    credentials_json: str  # Base64 encoded JSON


@router.put("/notifications/config", summary="Update Firebase Credentials")
async def update_firebase_config(
    body: FirebaseConfigRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Update Firebase credentials JSON in the database and reinitialize FCM."""
    from app.models.settings import SystemSetting
    from app.services.notification_service import init_firebase_from_db
    
    # 1. Update or create the setting in the database
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == 'firebase_credentials_json')
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = body.credentials_json
        setting.updated_at = datetime.utcnow()
    else:
        setting = SystemSetting(
            key='firebase_credentials_json',
            value=body.credentials_json,
            group='system',
            label='Firebase Credentials JSON',
            description='Firebase Service Account JSON (Base64)',
            is_secret=True
        )
        db.add(setting)
        
    await db.commit()
    
    # 2. Re-initialize Firebase Admin SDK dynamically
    await init_firebase_from_db()
    
    from app.services.notification_service import is_firebase_ready
    if not is_firebase_ready():
        raise HTTPException(
            status_code=400, 
            detail="فشل تهيئة Firebase. تأكد إن الملف صالح (Invalid Service Account JSON)."
        )
        
    return {"message": "✅ تم حفظ وتفعيل إعدادات Firebase بنجاح"}




@router.post("/notifications/send", summary="Send a push notification")
async def send_notification(
    body: SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Send a push notification.
    - broadcast: sends to ALL registered devices
    - user: sends to a specific user's devices
    - group: sends to multiple users' devices
    """
    if body.target_type not in ("broadcast", "user", "group"):
        raise HTTPException(status_code=400, detail="target_type must be 'broadcast', 'user', or 'group'")

    if body.target_type in ("user", "group") and not body.target_user_ids:
        raise HTTPException(status_code=400, detail="target_user_ids required for 'user' or 'group' target type")

    if not body.title.strip() or not body.body.strip():
        raise HTTPException(status_code=400, detail="Title and body cannot be empty")

    # Fetch FCM tokens based on target type
    if body.target_type == "broadcast":
        result = await db.execute(
            select(UserDeviceToken.fcm_token).where(UserDeviceToken.is_active == True)
        )
    else:
        result = await db.execute(
            select(UserDeviceToken.fcm_token).where(
                UserDeviceToken.is_active == True,
                UserDeviceToken.user_id.in_(body.target_user_ids)
            )
        )

    tokens = [row[0] for row in result.all()]

    if not tokens:
        raise HTTPException(
            status_code=404,
            detail="لا توجد أجهزة مسجلة للمستهدفين"  # No registered devices for targets
        )

    # Send via FCM
    success_count, fail_count, invalid_tokens = await send_push_notification(
        tokens=tokens,
        title=body.title.strip(),
        body=body.body.strip(),
        data=body.data_payload,
    )

    # Cleanup invalid tokens
    if invalid_tokens:
        await db.execute(
            delete(UserDeviceToken).where(UserDeviceToken.fcm_token.in_(invalid_tokens))
        )

    # Log the notification
    log_entry = NotificationLog(
        title=body.title.strip(),
        body=body.body.strip(),
        target_type=body.target_type,
        target_user_ids=body.target_user_ids,
        sent_count=success_count,
        failed_count=fail_count,
        data_payload=body.data_payload,
        sent_by=admin.id,
    )
    db.add(log_entry)
    await db.commit()

    return {
        "message": "✅ تم إرسال الإشعار",
        "sent_count": success_count,
        "failed_count": fail_count,
        "invalid_tokens_removed": len(invalid_tokens),
    }


@router.get("/notifications/history", summary="Get notification history")
async def get_notification_history(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Returns paginated list of sent notifications."""
    result = await db.execute(
        select(NotificationLog, User.fullname.label("admin_name"))
        .outerjoin(User, NotificationLog.sent_by == User.id)
        .order_by(NotificationLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.all()

    return [
        {
            "id": str(item.NotificationLog.id),
            "title": item.NotificationLog.title,
            "body": item.NotificationLog.body,
            "target_type": item.NotificationLog.target_type,
            "sent_count": item.NotificationLog.sent_count,
            "failed_count": item.NotificationLog.failed_count,
            "admin_name": item.admin_name or "System",
            "created_at": item.NotificationLog.created_at.isoformat() if item.NotificationLog.created_at else None,
        }
        for item in items
    ]


@router.delete("/notifications/{notification_id}", summary="Delete a notification log")
async def delete_notification_log(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Delete a notification log entry."""
    result = await db.execute(
        select(NotificationLog).where(NotificationLog.id == notification_id)
    )
    log_entry = result.scalar_one_or_none()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Notification log not found")

    await db.delete(log_entry)
    await db.commit()
    return {"message": "✅ تم حذف سجل الإشعار"}
