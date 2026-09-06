"""
Outbound email — password resets today, significant-move alerts once
Task #22 wires the scheduler up to it (see docs/DECISIONS.md).

Deliberately degrades to logging instead of failing when SMTP isn't
configured: a hackathon judge or a customer's first `git clone` should
never crash on a missing mail server. Swapping in a real provider
(SendGrid, SES, Postmark) later means implementing `_send` differently,
not touching any caller.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("pulse.notifications")


def _send(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        logger.info("[email:not-configured] to=%s subject=%r body=%r", to_email, subject, body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
    except Exception:
        # Notification delivery is never allowed to break the calling
        # request (a password-reset request must still return 200 even if
        # the mail server is down) — log loudly and move on.
        logger.exception("Failed to send email to %s", to_email)


def send_password_reset_email(to_email: str, raw_token: str) -> None:
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    _send(
        to_email,
        subject="Reset your Pulse password",
        body=(
            "We received a request to reset your Pulse password.\n\n"
            f"Reset it here: {reset_link}\n\n"
            f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes. "
            "If you didn't request this, you can ignore this email."
        ),
    )


def send_significant_move_alert(to_email: str, symbol: str, summary: str) -> None:
    _send(
        to_email,
        subject=f"Pulse alert: {symbol} moved significantly",
        body=summary,
    )
