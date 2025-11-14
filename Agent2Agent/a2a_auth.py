import os
from typing import Optional

try:
    # Starlette is the underlying ASGI used by FastAPI and ADK apps
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
except ImportError:
    # Fallback imports if starlette is not available (should be present)
    BaseHTTPMiddleware = object  # type: ignore
    JSONResponse = None  # type: ignore


def _get_expected_api_key() -> Optional[str]:
    return os.getenv("A2A_API_KEY")


def _get_expected_bearer_token() -> Optional[str]:
    return os.getenv("A2A_BEARER_TOKEN")


class A2aAuthMiddleware(BaseHTTPMiddleware):
    """
    Simple auth middleware for A2A servers.

    - Enforces either an `X-A2A-API-Key` header that matches `A2A_API_KEY`
      or an `Authorization: Bearer <token>` that matches `A2A_BEARER_TOKEN`.
    - Allows public access to the agent card `/.well-known/agent-card.json`.
    - Returns 401 or 403 with a JSON error body for unauthenticated requests.
    """

    async def dispatch(self, request, call_next):  # type: ignore[override]
        path: str = request.url.path
        # Allow public agent card
        if path.startswith("/.well-known/agent-card.json"):
            return await call_next(request)

        # Only enforce auth for A2A endpoints
        if path.startswith("/a2a") or path.startswith("/agents") or path.startswith("/run"):
            expected_key = _get_expected_api_key()
            expected_bearer = _get_expected_bearer_token()

            provided_key = request.headers.get("X-A2A-API-Key")
            auth_header = request.headers.get("Authorization", "")
            provided_bearer = None
            if auth_header.lower().startswith("bearer "):
                provided_bearer = auth_header[7:].strip()

            # If neither auth method is configured, allow (development default)
            if not expected_key and not expected_bearer:
                return await call_next(request)

            # API key check
            if expected_key and provided_key == expected_key:
                return await call_next(request)

            # Bearer token check
            if expected_bearer and provided_bearer == expected_bearer:
                return await call_next(request)

            # Unauthorized
            if JSONResponse is not None:
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Invalid or missing API key / bearer token"},
                    status_code=401 if not provided_key and not provided_bearer else 403,
                )

        # Non-A2A paths pass through
        return await call_next(request)


def attach_auth_middleware(app) -> None:
    """Attach auth middleware to the given ASGI app if starlette is available."""
    if hasattr(app, "add_middleware") and BaseHTTPMiddleware is not object:
        app.add_middleware(A2aAuthMiddleware)