import asyncio
import smtplib
import logging
from html import escape as _esc
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import settings
from app.database import get_db
from app.models import Alert, DemoRequest
from app.crypto import decrypt_secret

logger = logging.getLogger(__name__)


# ── Home Assistant Integration ─────────────────────────────────────────────

async def notify_home_assistant(alert: Alert):
    """
    Two-step HA notification, scoped to the alert's own organization:
      1. Update a sensor entity so HA dashboard shows current state
      2. Trigger a webhook so automations can fire instantly

    Uses the org's own Home Assistant credentials (never a shared/global one),
    so one tenant's incident can never reach another tenant's devices.
    """
    db = get_db()
    org = await db.organizations.find_one({"org_id": alert.org_id})
    if not org:
        return
    ha_url = org.get("ha_url") or ""
    ha_token = decrypt_secret(org["ha_token_encrypted"]) if org.get("ha_token_encrypted") else None
    if not ha_url or not ha_token:
        return
    ha_url = ha_url.rstrip("/")

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }

    sensor_payload = {
        "state": alert.hazard_type,
        "attributes": {
            "friendly_name":  "Firemax Hazard Sensor",
            "camera_id":      alert.camera_id,
            "camera_name":    alert.camera_name,
            "hazard_type":    alert.hazard_type,
            "confidence":     f"{alert.confidence:.0%}",
            "confidence_raw": alert.confidence,
            "timestamp":      str(alert.timestamp),
            "icon":           "mdi:fire-alert",
        }
    }

    webhook_payload = {
        "hazard_type":  alert.hazard_type,
        "camera_name":  alert.camera_name,
        "confidence":   alert.confidence,
        "timestamp":    str(alert.timestamp),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Update sensor state (visible in HA dashboard)
            r1 = await client.post(
                f"{ha_url}/api/states/sensor.firemax_hazard",
                json=sensor_payload,
                headers=headers,
            )
            # Trigger webhook (fires automations)
            r2 = await client.post(
                f"{ha_url}/api/webhook/{settings.HA_WEBHOOK_ID}",
                json=webhook_payload,
            )
            logger.info(
                f"[HA] sensor={r1.status_code}  webhook={r2.status_code}  "
                f"hazard={alert.hazard_type}  cam={alert.camera_name}"
            )
    except Exception as exc:
        logger.error(f"[HA] Failed to notify Home Assistant: {exc}")


# ── Twilio (authority calls/SMS on confirmed incidents) ─────────────────────

def _twilio_client():
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        return None
    from twilio.rest import Client
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


async def notify_authorities(alert: Alert):
    """Call/SMS every configured authority contact. Only invoked when a human
    operator has confirmed the detection as a real incident."""
    client = _twilio_client()
    if not client:
        return

    db = get_db()
    contacts = await db.authority_contacts.find({"org_id": alert.org_id}).to_list(50)
    if not contacts:
        return

    message = (
        f"FiremeX ALERT: {alert.hazard_type.upper()} confirmed at {alert.camera_name} "
        f"({alert.zone}), {alert.confidence:.0%} confidence. Incident {alert.incident_code}."
    )
    twiml = f"<Response><Say>{message}</Say></Response>"

    loop = asyncio.get_event_loop()

    def _send(contact):
        try:
            if contact["notify_via"] in ("sms", "both"):
                client.messages.create(to=contact["phone"], from_=settings.TWILIO_FROM_NUMBER, body=message)
            if contact["notify_via"] in ("call", "both"):
                client.calls.create(to=contact["phone"], from_=settings.TWILIO_FROM_NUMBER, twiml=twiml)
            logger.info(f"[twilio] Notified {contact['name']} ({contact['phone']}) via {contact['notify_via']}")
        except Exception as exc:
            logger.error(f"[twilio] Failed to notify {contact.get('name')}: {exc}")

    await asyncio.gather(*[
        loop.run_in_executor(None, _send, contact) for contact in contacts
    ])


# ── Email Notification ─────────────────────────────────────────────────────

async def send_alert_email(alert: Alert):
    if not all([settings.SMTP_HOST, settings.SMTP_USER,
                settings.SMTP_PASS, settings.ALERT_EMAIL]):
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"[FIREMAX] {alert.hazard_type.upper()} DETECTED — {alert.camera_name}"
        )
        msg["From"] = settings.SMTP_USER
        msg["To"]   = settings.ALERT_EMAIL

        body = f"""
        <div style="font-family:sans-serif;max-width:520px">
          <h2 style="color:#EF4444">&#128293; Hazard Detected</h2>
          <table style="border-collapse:collapse;width:100%">
            <tr><td style="padding:6px;color:#6B7280">Type</td>
                <td style="padding:6px;font-weight:bold">{_esc(alert.hazard_type.upper())}</td></tr>
            <tr><td style="padding:6px;color:#6B7280">Camera</td>
                <td style="padding:6px">{_esc(alert.camera_name)}</td></tr>
            <tr><td style="padding:6px;color:#6B7280">Confidence</td>
                <td style="padding:6px">{alert.confidence:.0%}</td></tr>
            <tr><td style="padding:6px;color:#6B7280">Time</td>
                <td style="padding:6px">{_esc(str(alert.timestamp))}</td></tr>
          </table>
        """
        if alert.frame_b64:
            body += f'<img src="data:image/jpeg;base64,{alert.frame_b64}" style="width:100%;margin-top:12px;border-radius:6px"/>'
        body += "</div>"

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
            srv.starttls()
            srv.login(settings.SMTP_USER, settings.SMTP_PASS)
            srv.sendmail(settings.SMTP_USER, settings.ALERT_EMAIL, msg.as_string())

        logger.info(f"[email] Alert sent for {alert.camera_name}")
    except Exception as exc:
        logger.error(f"[email] Failed: {exc}")


async def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Returns True if the email was actually sent (SMTP configured), False
    if SMTP isn't set up — callers fall back to logging the link so local/dev
    use still works without a mail server."""
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASS]):
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your FiremeX password"
        msg["From"] = settings.SMTP_USER
        msg["To"]   = to_email

        body = f"""
        <div style="font-family:sans-serif;max-width:480px">
          <h2 style="color:#111827">Reset your password</h2>
          <p style="color:#4B5563">
            Click the button below to choose a new password. This link expires in 1 hour.
          </p>
          <p><a href="{reset_link}"
                style="display:inline-block;background:#C2410C;color:#fff;padding:10px 20px;
                       border-radius:8px;text-decoration:none;font-weight:600">Reset Password</a></p>
          <p style="color:#9CA3AF;font-size:12px">
            If you didn't request this, you can safely ignore this email.
          </p>
        </div>
        """
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
            srv.starttls()
            srv.login(settings.SMTP_USER, settings.SMTP_PASS)
            srv.sendmail(settings.SMTP_USER, to_email, msg.as_string())

        logger.info(f"[email] Password reset link sent to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"[email] Failed to send password reset: {exc}")
        return False


async def send_demo_request_email(request: DemoRequest) -> bool:
    """Notifies sales of a new demo request. Returns False (silently) if no
    destination is configured — the request is still saved to the database
    either way, so nothing is lost."""
    to_email = settings.SALES_EMAIL or settings.ALERT_EMAIL
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASS, to_email]):
        return False

    try:
        msg = MIMEMultipart("alternative")
        # This endpoint is public/unauthenticated, so every field is attacker-
        # controlled — escape all of them to prevent HTML/link injection into
        # the email our staff opens. The Subject is a plain header (not HTML).
        msg["Subject"] = f"New FiremeX demo request — {request.company}"
        msg["From"] = settings.SMTP_USER
        msg["To"]   = to_email

        body = f"""
        <div style="font-family:sans-serif;max-width:480px">
          <h2 style="color:#111827">New demo request</h2>
          <table style="border-collapse:collapse;width:100%">
            <tr><td style="padding:6px;color:#6B7280">Name</td><td style="padding:6px;font-weight:bold">{_esc(request.name)}</td></tr>
            <tr><td style="padding:6px;color:#6B7280">Email</td><td style="padding:6px">{_esc(request.email)}</td></tr>
            <tr><td style="padding:6px;color:#6B7280">Company</td><td style="padding:6px">{_esc(request.company)}</td></tr>
            <tr><td style="padding:6px;color:#6B7280">Phone</td><td style="padding:6px">{_esc(request.phone or "—")}</td></tr>
          </table>
          {f'<p style="color:#4B5563;margin-top:12px">{_esc(request.message)}</p>' if request.message else ''}
        </div>
        """
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
            srv.starttls()
            srv.login(settings.SMTP_USER, settings.SMTP_PASS)
            srv.sendmail(settings.SMTP_USER, to_email, msg.as_string())

        logger.info(f"[email] Demo request notification sent for {request.company}")
        return True
    except Exception as exc:
        logger.error(f"[email] Failed to send demo request notification: {exc}")
        return False
