"""
Shared slowapi Limiter instance.

Lives in its own module (rather than on app.main) so route modules can
import and apply it with @limiter.limit(...) without a circular import
back to main.py, which is what wires it into the FastAPI app and its
rate-limit-exceeded exception handler.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])
