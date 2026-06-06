import os
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

# Brevo HTTP API (works on Railway - no SMTP port blocking)
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
MAIL_FROM = os.getenv("MAIL_FROM", "sirahmedayman@gmail.com")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Etzan")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


async def _send_email(to_email: str, subject: str, html_content: str):
    """Send email using Brevo HTTP API (bypasses SMTP port blocking on Railway)"""
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "sender": {"name": MAIL_FROM_NAME, "email": MAIL_FROM},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(BREVO_API_URL, json=payload, headers=headers)
        if response.status_code not in [200, 201]:
            print(f"Email send failed: {response.status_code} - {response.text}")
            raise Exception(f"Failed to send email: {response.text}")
        print(f"Email sent successfully to {to_email}")


async def send_reset_password_email(email_to: str, token: str):
    html = f"""
    <div dir="rtl" style="font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #f9f9f9; padding: 40px 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background-color: #2c3e50; padding: 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Etzan</h1>
            </div>
            <div style="padding: 40px 30px; text-align: center;">
                <h2 style="color: #333333; margin-top: 0; margin-bottom: 20px; font-size: 22px;">إعادة تعيين كلمة المرور</h2>
                <p style="color: #666666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    لقد تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بحسابك.<br>يرجى استخدام الكود أدناه لإتمام هذه العملية:
                </p>
                <div style="background-color: #f8fafc; border: 2px dashed #cbd5e0; border-radius: 8px; padding: 20px; margin: 0 auto 30px; display: inline-block;">
                    <span style="font-family: monospace; font-size: 32px; font-weight: bold; color: #2c3e50; letter-spacing: 5px;" dir="ltr">{token}</span>
                </div>
                <p style="color: #888888; font-size: 14px; line-height: 1.5; margin-bottom: 0;">
                    هذا الكود صالح لمدة 15 دقيقة فقط.<br>
                    إذا لم تقم بهذا الطلب، يمكنك تجاهل هذه الرسالة بأمان.
                </p>
            </div>
            <div style="background-color: #f8fafc; padding: 15px; text-align: center; border-top: 1px solid #edf2f7;">
                <p style="color: #a0aec0; font-size: 12px; margin: 0;">&copy; Etzan. جميع الحقوق محفوظة.</p>
            </div>
        </div>
    </div>
    """
    await _send_email(email_to, "إعادة تعيين كلمة المرور - Etzan", html)
