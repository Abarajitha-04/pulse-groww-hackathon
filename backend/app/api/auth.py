from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    generate_password_reset_token,
    hash_token,
)
from app.db.session import get_db
from app.models.models import User, RefreshToken, PasswordResetToken
from app.schemas import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    LogoutRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    MessageResponse,
)
from app.services.notification_service import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access = create_access_token(subject=user.id)
    raw_refresh, refresh_hash, expires_at = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=expires_at))
    db.commit()
    return TokenResponse(access_token=access, refresh_token=raw_refresh)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def signup(request: Request, payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        # Same error for "no such user" and "wrong password" — don't leak
        # which one it was (a classic account-enumeration leak).
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """Rotates the refresh token on every use (the old one is revoked, a new
    one issued) rather than just re-validating it. This is what lets us
    detect refresh-token theft: if a revoked token is ever presented again,
    it means two parties have the same token and both must be logged out —
    see the reuse check below."""
    token_hash = hash_token(payload.refresh_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if record is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)

    if record.revoked_at is not None:
        # Reuse of an already-rotated-away token: treat as compromise and
        # revoke every refresh token this user holds.
        db.query(RefreshToken).filter(
            RefreshToken.user_id == record.user_id, RefreshToken.revoked_at.is_(None)
        ).update({"revoked_at": now})
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; all sessions revoked")

    if expires_at < now:
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(User).filter(User.id == record.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    record.revoked_at = now
    db.add(record)
    db.commit()

    return _issue_tokens(db, user)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        db.add(record)
        db.commit()
    # Always 200 — logging out an already-invalid token isn't an error the
    # client needs to react to.
    return MessageResponse(message="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke every active session for the current user — e.g. 'log out
    everywhere' after a password change or a lost device."""
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()
    return MessageResponse(message="All sessions revoked")


@router.post("/request-password-reset", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def request_password_reset(request: Request, payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is not None and user.is_active:
        raw, token_hash, expires_at = generate_password_reset_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        db.commit()
        send_password_reset_email(user.email, raw)
    # Identical response whether or not the email exists — otherwise this
    # endpoint becomes an account-enumeration oracle.
    return MessageResponse(message="If that email is registered, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def reset_password(request: Request, payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.token)
    record = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    if record is None or record.used_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or already-used reset token")

    expires_at = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user = db.query(User).filter(User.id == record.user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.password_hash = hash_password(payload.new_password)
    record.used_at = datetime.now(timezone.utc)
    db.add(user)
    db.add(record)
    # A password reset is a strong signal of possible compromise — revoke
    # every existing session so a stolen access/refresh token pair from
    # before the reset stops working immediately.
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()

    return MessageResponse(message="Password has been reset")
