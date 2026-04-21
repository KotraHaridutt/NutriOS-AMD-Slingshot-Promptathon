"""
NutriOS — JWT Authentication Middleware

Implements JWT token verification as a FastAPI dependency.
All routes except /health require a valid JWT token.

For hackathon demo, includes a /auth/demo-token endpoint
to generate test tokens without a full auth flow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import get_settings

logger = logging.getLogger(__name__)

# Security scheme — extracts Bearer token from Authorization header
security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    FastAPI dependency that validates the JWT token and extracts the user_id.

    Usage in routes:
        @router.post("/nudge")
        async def nudge(user_id: str = Depends(get_current_user_id)):
            ...

    Args:
        credentials: The Bearer token from the Authorization header.

    Returns:
        The user_id extracted from the JWT payload.

    Raises:
        HTTPException 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user identifier.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check expiration (jose does this, but let's be explicit)
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please obtain a new one.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug("Authenticated user: %s", user_id)
        return user_id

    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please authenticate again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(
    user_id: str,
    name: str = "Demo User",
    extra_claims: Optional[dict] = None,
) -> str:
    """
    Create a signed JWT access token.

    Used by the demo token endpoint and for testing.

    Args:
        user_id: The user's unique identifier (becomes the "sub" claim).
        name: The user's display name.
        extra_claims: Additional claims to include in the payload.

    Returns:
        Signed JWT string.
    """
    settings = get_settings()

    payload = {
        "sub": user_id,
        "name": name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }

    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    logger.info("Access token created for user: %s", user_id)
    return token
