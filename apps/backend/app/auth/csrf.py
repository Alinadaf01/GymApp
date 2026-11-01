"""CSRF protection for cookie-authenticated API calls.

State-changing requests must carry `X-Requested-With: fetch`. A custom header
forces a CORS preflight, which only the panel origin passes. If an Origin header
is present it must equal the panel origin.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Endpoints authenticated by other means (e.g. Telegram secret token header)
EXEMPT_PATHS = {"/api/telegram/webhook"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and request.url.path not in EXEMPT_PATHS:
            origin = request.headers.get("origin")
            if origin is not None and origin.rstrip("/") != get_settings().frontend_url.rstrip("/"):
                return JSONResponse({"detail": "درخواست نامعتبر است."}, status_code=403)
            if request.headers.get("x-requested-with") != "fetch":
                return JSONResponse({"detail": "درخواست نامعتبر است."}, status_code=403)
        return await call_next(request)
