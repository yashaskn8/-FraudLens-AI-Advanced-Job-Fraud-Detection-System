"""
Middleware for rate limiting, CORS, and request logging.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

logger = logging.getLogger("trusthire")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} — "
            f"{response.status_code} — {process_time:.3f}s"
        )
        response.headers["X-Process-Time"] = str(process_time)
        return response
