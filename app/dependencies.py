import hmac
import logging

from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

# Security dependencies for VAPI and admin endpoints


async def verify_vapi_secret(request: Request) -> None:
    """Verify the X-Vapi-Secret header matches our configured secret.

    If VAPI_SERVER_SECRET is empty/unset, skip validation (dev mode).
    """
    secret = settings.VAPI_SERVER_SECRET
    if not secret:
        return
    header = request.headers.get("x-vapi-secret", "")
    if not hmac.compare_digest(header, secret):
        logger.warning("VAPI secret mismatch from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=403, detail="Invalid VAPI secret")


async def verify_admin_key(request: Request) -> None:
    """Verify the X-Admin-Key header for admin endpoints.

    If ADMIN_API_KEY is empty/unset, skip validation (dev mode).
    """
    key = settings.ADMIN_API_KEY
    if not key:
        return
    header = request.headers.get("x-admin-key", "")
    if not hmac.compare_digest(header, key):
        logger.warning("Admin key mismatch from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=403, detail="Invalid admin key")
