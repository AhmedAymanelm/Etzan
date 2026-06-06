from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
import httpx
import os
import uuid
from datetime import datetime, timedelta

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.payment import PaymentRecord
from app.models.subscription import UserSubscription

payment_router = APIRouter(
    prefix="/payment",
    tags=["Payment (Fawaterk)"]
)
limiter = Limiter(key_func=get_remote_address)


async def _get_setting(key: str, fallback_env: str = "", default: str = "") -> str:
    """Read a setting from system_settings DB, fallback to env var."""
    try:
        from app.database import async_session_maker
        from app.models.settings import SystemSetting
        from sqlalchemy.future import select as _select
        async with async_session_maker() as sess:
            res = await sess.execute(_select(SystemSetting).where(SystemSetting.key == key))
            row = res.scalar_one_or_none()
            if row and row.value:
                return row.value
    except Exception:
        pass
    return os.environ.get(fallback_env, default)


async def _get_fawaterk_config():
    """Returns all Fawaterk config from DB (or env fallback)."""
    api_key = await _get_setting("fawaterk_api_key", "FAWATERK_API_KEY")
    mode    = await _get_setting("fawaterk_mode",    "FAWATERK_MODE", "test")
    base    = "https://staging.fawaterk.com" if mode == "test" else "https://app.fawaterk.com"
    return api_key, mode, base


async def _create_subscription_for_user(user_id, payment_record_id, db: AsyncSession):
    """
    Creates a 30-day UserSubscription for a user linked to a payment record.
    Safe to call multiple times — skips if a subscription already exists for this payment.
    """
    # Guard: don't create duplicate subscriptions for the same payment
    if payment_record_id:
        existing = await db.execute(
            select(UserSubscription).where(
                UserSubscription.payment_record_id == payment_record_id
            )
        )
        if existing.scalar_one_or_none():
            return  # Already created for this payment

    now = datetime.utcnow()
    sub = UserSubscription(
        user_id=user_id,
        payment_record_id=payment_record_id,
        started_at=now,
        expires_at=now + timedelta(days=30),
        is_active=True,
        plan_type="monthly",
        granted_by_admin=False,
    )
    db.add(sub)
    # Caller is responsible for commit


class PaymentRequest(BaseModel):
    # 'amount' and 'currency' discouraged from being trusted from client side. We compute it server side.
    service_type: str = "monthly_subscription"
    payment_method_id: int = 0 # Default to 0 for generic checkout to show all methods

@payment_router.get("/price")
async def get_service_price(service_type: str = "monthly_subscription"):
    """
    Returns the current price for a requested service.
    Flutter should call this to display the correct price on the UI.
    """
    price_str = await _get_setting(f"price_{service_type}", default="250.00")
    currency = await _get_setting(f"currency_{service_type}", default="EGP")
    try:
        price = float(price_str)
        if price < 5.0:
            price = 250.00
    except ValueError:
        price = 250.00
    
    return {
        "service_type": service_type,
        "amount": price,
        "currency": currency
    }


@payment_router.get("/subscription-status")
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the current subscription status for the authenticated user.
    Flutter should call this on app launch to decide whether to show paywall.
    """
    now = datetime.utcnow()

    result = await db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.is_active == True,
            UserSubscription.expires_at > now,
        ).order_by(UserSubscription.expires_at.desc())
    )
    active_sub = result.scalar_one_or_none()

    if active_sub:
        days_remaining = (active_sub.expires_at - now).days
        return {
            "has_active_subscription": True,
            "expires_at": active_sub.expires_at.isoformat(),
            "days_remaining": days_remaining,
            "plan_type": active_sub.plan_type,
            "free_trial_used": current_user.free_trial_used,
        }

    return {
        "has_active_subscription": False,
        "expires_at": None,
        "days_remaining": 0,
        "plan_type": None,
        "free_trial_used": current_user.free_trial_used,
    }


@payment_router.get("/methods")
async def get_payment_methods():
    """
    Fetch all enabled payment methods from Fawaterk for the connected account.
    """
    api_key, _, api_base = await _get_fawaterk_config()
    if not api_key:
        raise HTTPException(status_code=500, detail="Fawaterk API key is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{api_base}/api/v2/getPaymentmethods", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Fawaterk API Error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@payment_router.post("/checkout")
@limiter.limit("10/minute")
async def create_checkout_session(request: Request, body: PaymentRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Create a Fawaterk Payment Invoice for a monthly subscription.
    The amount and currency are securely fetched from the database settings to prevent client-side tampering.
    """
    api_key, mode, api_base = await _get_fawaterk_config()

    if not api_key:
        raise HTTPException(status_code=500, detail="Fawaterk credentials are not configured")

    # Securely determine the amount and currency from the server config
    price_str = await _get_setting(f"price_{body.service_type}", default="250.00")
    currency = await _get_setting(f"currency_{body.service_type}", default="EGP")
    
    try:
        amount = float(price_str)
        if amount < 5.0:
            amount = 250.00
    except (ValueError, TypeError):
        amount = 250.00
        
    order_id = f"ORD_{str(uuid.uuid4()).replace('-', '')[:8]}"

    payload = {
        "cartTotal": str(amount),
        "currency": currency,
        "customer": {
            "first_name": current_user.fullname.split(' ')[0] if current_user.fullname else "Customer",
            "last_name": current_user.fullname.split(' ')[-1] if current_user.fullname and ' ' in current_user.fullname else "Name",
            "email": current_user.email,
            "phone": "01000000000",
            "address": "Egypt"
        },
        "redirectionUrls": {
            "successUrl": "https://baytalhayat.redirect/payment-success",
            "failUrl": "https://baytalhayat.redirect/payment-error",
            "pendingUrl": "https://baytalhayat.redirect/payment-pending"
        },
        "cartItems": [
            {
                "name": f"اشتراك شهري - Etzan",
                "price": str(amount),
                "quantity": "1"
            }
        ]
    }

    if body.payment_method_id > 0:
        payload["payment_method_id"] = body.payment_method_id
        payload["redirectOption"] = True
        endpoint = "/api/v2/invoiceInitPay"
    else:
        endpoint = "/api/v2/createInvoiceLink"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(f"{api_base}{endpoint}", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            fawaterk_data = data.get("data", {})
            
            if endpoint == "/api/v2/invoiceInitPay":
                session_id = str(fawaterk_data.get("invoice_id"))
                checkout_url = fawaterk_data.get("payment_data", {}).get("redirectTo")
                if not checkout_url:
                    invoice_key = fawaterk_data.get("invoice_key", "")
                    checkout_url = f"{api_base}/invoice/{session_id}/{invoice_key}"
            else:
                session_id = str(fawaterk_data.get("invoiceId"))
                checkout_url = fawaterk_data.get("url")

            payment_record = PaymentRecord(
                user_id=current_user.id,
                order_id=order_id,
                session_id=session_id,
                amount=amount,
                currency=currency,
                service_type=body.service_type,
                status="PENDING"
            )
            db.add(payment_record)
            await db.commit()

            return {
                "message": "Payment session created successfully",
                "session_id": session_id,
                "session_url": checkout_url,
                "order_id": order_id,
                "amount": amount
            }
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Fawaterk API Error: {e.response.text}")
        except Exception as e:
            import traceback
            trace_str = traceback.format_exc()
            print(f"Checkout Error: {trace_str}")
            raise HTTPException(status_code=500, detail=repr(e))

@payment_router.post("/verify")
async def verify_payment(session_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Called by the Flutter app after the checkout UI returns.
    Verifies the payment session status with Fawaterk, updates the DB,
    and creates a UserSubscription if the payment is confirmed.
    """
    api_key, _, api_base = await _get_fawaterk_config()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{api_base}/api/v2/getInvoiceData/{session_id}", headers=headers)
            response.raise_for_status()
            data = response.json().get("data", {})
            raw_status = data.get("invoice_status") or data.get("status_text", "")
            fawaterk_status = raw_status.lower()

            result = await db.execute(select(PaymentRecord).where(PaymentRecord.session_id == session_id, PaymentRecord.user_id == current_user.id))
            payment_record = result.scalar_one_or_none()

            if not payment_record:
                raise HTTPException(status_code=404, detail="Payment record not found")

            if fawaterk_status == "paid":
                payment_record.status = "SUCCESS"
                # ── Create subscription ──────────────────────────────────────
                await _create_subscription_for_user(
                    user_id=current_user.id,
                    payment_record_id=payment_record.id,
                    db=db
                )
            elif fawaterk_status in ("canceled", "failed"):
                payment_record.status = "FAILED"
            else:
                payment_record.status = "PENDING"

            payment_record.payment_method = data.get("payment_method")
            await db.commit()

            return {
                "status": payment_record.status,
                "order_id": payment_record.order_id,
                "amount": payment_record.amount,
                "subscription_created": fawaterk_status == "paid"
            }
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Fawaterk API Error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@payment_router.get("/status/{session_id}")
async def get_payment_status(session_id: str):
    """
    Get the status of a Fawaterk Payment Invoice.
    """
    api_key, _, api_base = await _get_fawaterk_config()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{api_base}/api/v2/getInvoiceData/{session_id}", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Fawaterk API Error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@payment_router.post("/webhook")
async def fawaterk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint to receive payment status updates from Fawaterk.
    Fawaterk sends a POST with JSON body.
    On confirmed payment, automatically creates a 30-day UserSubscription.
    """
    import json
    
    body_bytes = await request.body()
    raw_body = body_bytes.decode("utf-8") if body_bytes else "{}"
    
    try:
        payload = json.loads(raw_body)
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    print("================ FAWATERK WEBHOOK ================")
    print(payload)
    print("==================================================")

    # ── Extract fields ────────────────────────────────────────────────────────
    invoice_id = str(payload.get("invoice_id"))
    raw_webhook_status = payload.get("invoice_status") or payload.get("status_text", "")
    fawaterk_status = raw_webhook_status.lower()

    if not invoice_id:
        return {"status": "ignored", "reason": "no_invoice_id"}

    # ── Security check: Fetch actual invoice status from Fawaterk API ---------
    api_key, _, api_base = await _get_fawaterk_config()
    if not api_key:
        return {"status": "ignored", "reason": "no_api_key"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    verified_status = "pending"
    payment_method = ""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{api_base}/api/v2/getInvoiceData/{invoice_id}", headers=headers)
            response.raise_for_status()
            fetched_data = response.json().get("data", {})
            raw_v_status = fetched_data.get("invoice_status") or fetched_data.get("status_text", "")
            verified_status = raw_v_status.lower()
            payment_method = fetched_data.get("payment_method", "")
        except Exception as e:
            print(f"[WARN] Webhook: Failed to verify invoice {invoice_id} status via API: {e}")
            return {"status": "ignored", "reason": "verification_failed"}

    # ── Find payment record ───────────────────────────────────────────────────
    result = await db.execute(
        select(PaymentRecord).where(
            PaymentRecord.session_id == invoice_id
        )
    )
    payment = result.scalar_one_or_none()

    if not payment:
        print(f"[WARN] Webhook: no PaymentRecord found for session={invoice_id}")
        return {"status": "not_found"}

    # ── Map Fawaterk status → our status ──────────────────────────────────────
    if verified_status == "paid":
        payment.status = "SUCCESS"
        # ── Create subscription for the user ──────────────────────────────────
        await _create_subscription_for_user(
            user_id=payment.user_id,
            payment_record_id=payment.id,
            db=db
        )
    elif verified_status in ("canceled", "failed"):
        payment.status = "FAILED"
    else:
        payment.status = "PENDING"

    if payment_method:
        payment.payment_method = payment_method

    payment.updated_at = datetime.utcnow()
    await db.commit()

    print(f"[OK] Payment {payment.order_id} -> {payment.status}")
    return {"status": "ok", "order_id": payment.order_id, "new_status": payment.status}
