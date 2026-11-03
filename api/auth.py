"""Supabase access-token verification.

The frontend authenticates with Supabase and sends the resulting access token
as `Authorization: Bearer <jwt>`. Supabase signs these with the project's JWT
secret (HS256), so we can verify them locally with no network round-trip.

When CRB_REQUIRE_AUTH is off (local dev), the API is open and every request is
treated as authenticated. When it is on, a valid token is required.
"""

from typing import Optional

import config

try:
    import jwt  # PyJWT
    from jwt import InvalidTokenError
except ImportError:  # pragma: no cover - dependency guard
    jwt = None

    class InvalidTokenError(Exception):
        pass


class AuthError(Exception):
    """Raised when a request must be rejected for auth reasons."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


def _bearer_token(request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def verify_token(token: str) -> dict:
    """Decode and validate a Supabase access token, returning its claims."""
    if jwt is None:
        raise AuthError("Server auth dependency (PyJWT) is not installed.", 500)
    if not config.SUPABASE_JWT_SECRET:
        raise AuthError("Server is missing SUPABASE_JWT_SECRET.", 500)

    try:
        claims = jwt.decode(
            token,
            config.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=config.SUPABASE_JWT_AUD,
        )
    except InvalidTokenError as exc:
        raise AuthError(f"Invalid or expired session: {exc}") from exc

    return claims


def user_from_claims(claims: dict) -> dict:
    return {
        "id": claims.get("sub"),
        "email": claims.get("email"),
        "role": claims.get("role"),
    }


def authenticate(request) -> Optional[dict]:
    """Resolve the caller.

    Returns a user dict when a valid token is present. Raises AuthError when
    auth is required but missing/invalid. Returns None for anonymous callers
    when auth is not required.
    """
    token = _bearer_token(request)

    if token:
        return user_from_claims(verify_token(token))

    if config.REQUIRE_AUTH:
        raise AuthError("Sign in to use this API.")

    return None  # anonymous, allowed only because auth is not required
