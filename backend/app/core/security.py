import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from app.core.config import settings

# Using bcrypt directly rather than through passlib: passlib's CryptContext
# has a known incompatibility with bcrypt>=4.1 (it probes for a bug-detection
# hash in a way that breaks on newer bcrypt builds). bcrypt itself is the
# actual hashing implementation either way, so this removes a dependency
# without losing anything.
_BCRYPT_MAX_BYTES = 72  # bcrypt's own input limit


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(truncated, password_hash.encode("utf-8"))


# --- Access tokens (short-lived JWT, stateless) ---------------------------
#
# Access tokens are deliberately short-lived (30 min default) and never
# checked against the database — that's what makes them cheap to verify on
# every request. The trade-off, and the reason refresh tokens exist below,
# is that a leaked/compromised access token is valid until it naturally
# expires; there is no way to revoke one early. Keeping the window short
# bounds that exposure.


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# --- Refresh tokens (opaque, server-side, revocable) -----------------------
#
# Unlike access tokens, refresh tokens are stored in the database as a
# hash (app/models/models.py:RefreshToken) — this is what makes logout and
# "revoke all sessions" actually possible. The value handed to the client
# is a high-entropy random string, never a JWT; there's nothing to decode,
# only a hash to look up.


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Returns (raw_token_for_client, hash_for_storage, expires_at)."""
    raw = secrets.token_urlsafe(48)
    token_hash = hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw, token_hash, expires_at


def hash_token(raw_token: str) -> str:
    """SHA-256 is fine here (not bcrypt): this hashes a high-entropy random
    token, not a low-entropy human password, so there's no brute-force
    concern that would call for a slow KDF."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_password_reset_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(32)
    token_hash = hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    return raw, token_hash, expires_at
