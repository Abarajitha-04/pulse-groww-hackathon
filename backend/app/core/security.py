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
