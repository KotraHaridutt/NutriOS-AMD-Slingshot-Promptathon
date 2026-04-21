"""
NutriOS — FastAPI Application Entrypoint

Context-aware food intelligence system.
NOT a calorie tracker. NutriOS helps you decide what you're
about to eat — based on your schedule, location, activity,
and past patterns.

Stack: FastAPI · Gemini AI · Google Maps · Google Calendar · Firestore
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from middleware.auth import create_access_token, get_current_user_id
from models.schemas import (
    ErrorResponse,
    HealthResponse,
    TokenResponse,
    UserProfile,
    UserProfileUpdate,
)
from routers import coach, log, nudge, report
from services import firestore_svc

# ── Logging Setup ──────────────────────────────────────────────
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nutrios")


# ── App Initialization ─────────────────────────────────────────
app = FastAPI(
    title="NutriOS",
    description=(
        "Context-aware food intelligence system. "
        "Proactive food nudges based on your schedule, location, "
        "activity, and meal history. Powered by Gemini AI."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ────────────────────────────────────────────
# Allow all origins for Codespace/demo. Restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ──────────────────────────────────────────
app.include_router(nudge.router)
app.include_router(log.router)
app.include_router(coach.router)
app.include_router(report.router)

# ── Serve Static Files (Frontend UI) ─────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ═══════════════════════════════════════════════════════════════
# ROOT + HEALTH ENDPOINTS (no auth required)
# ═══════════════════════════════════════════════════════════════


@app.get("/", tags=["System"], summary="NutriOS Web UI", include_in_schema=False)
async def root():
    """Serve the NutriOS frontend UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return HealthResponse(
        status="healthy",
        service="nutrios",
        version="1.0.0",
        environment=settings.environment,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Health check endpoint for load balancers and Cloud Run. No authentication required.",
)
async def health_check() -> HealthResponse:
    """Health check — used by Cloud Run, Docker, and load balancers."""
    return HealthResponse(
        status="healthy",
        service="nutrios",
        version="1.0.0",
        environment=settings.environment,
    )


# ═══════════════════════════════════════════════════════════════
# AUTH DEMO ENDPOINT (for testing — generates JWT tokens)
# ═══════════════════════════════════════════════════════════════


@app.post(
    "/auth/demo-token",
    response_model=TokenResponse,
    tags=["Auth"],
    summary="Generate demo JWT token",
    description=(
        "Generate a JWT token for testing/demo purposes. "
        "In production, replace this with your real auth provider "
        "(Firebase Auth, Auth0, etc.)."
    ),
)
async def generate_demo_token(
    user_id: str = "demo_user_001",
    name: str = "Demo User",
) -> TokenResponse:
    """
    Generate a demo JWT token for testing.

    This endpoint is for hackathon demo purposes only.
    In production, use a real authentication provider.
    """
    token = create_access_token(user_id=user_id, name=name)

    # Also create a demo profile if it doesn't exist
    profile = await firestore_svc.get_user_profile(user_id)
    if profile is None:
        await firestore_svc.create_or_update_profile(user_id, {
            "user_id": user_id,
            "name": name,
            "goal": "eat_healthier",
            "dietary_restrictions": [],
            "daily_calorie_target": 2000,
            "timezone": "UTC",
        })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiry_hours * 3600,
        message=f"Demo token generated for '{name}'. Use as Bearer token in Authorization header.",
    )


# ═══════════════════════════════════════════════════════════════
# PROFILE ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@app.get(
    "/profile",
    response_model=UserProfile,
    tags=["Profile"],
    summary="Get user profile",
)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
) -> UserProfile:
    """Fetch the current user's profile and goals."""
    profile = await firestore_svc.get_user_profile(user_id)
    if profile is None:
        # Create default profile
        profile = {
            "user_id": user_id,
            "name": "NutriOS User",
            "goal": "eat_healthier",
            "dietary_restrictions": [],
            "daily_calorie_target": 2000,
            "timezone": "UTC",
        }
        await firestore_svc.create_or_update_profile(user_id, profile)

    return UserProfile(**profile)


@app.put(
    "/profile",
    response_model=UserProfile,
    tags=["Profile"],
    summary="Update user profile",
)
async def update_profile(
    update: UserProfileUpdate,
    user_id: str = Depends(get_current_user_id),
) -> UserProfile:
    """Update the current user's profile and goals."""
    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        profile = await firestore_svc.get_user_profile(user_id)
        return UserProfile(**profile) if profile else UserProfile(user_id=user_id, name="User")

    await firestore_svc.create_or_update_profile(user_id, update_data)
    updated_profile = await firestore_svc.get_user_profile(user_id)
    return UserProfile(**updated_profile)


# ═══════════════════════════════════════════════════════════════
# GLOBAL ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler with human-readable message."""
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="not_found",
            message="The requested endpoint does not exist. Check /docs for available routes.",
        ).model_dump(),
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Custom 500 handler — never expose stack traces."""
    logger.error("Internal server error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            message="Something went wrong on our end. Please try again.",
        ).model_dump(),
    )


# ═══════════════════════════════════════════════════════════════
# STARTUP EVENT
# ═══════════════════════════════════════════════════════════════


@app.on_event("startup")
async def startup_event():
    """Log startup info."""
    logger.info("=" * 60)
    logger.info("  🍎 NutriOS v1.0.0 starting up")
    logger.info("  Environment: %s", settings.environment)
    logger.info("  Gemini Model: %s", settings.gemini_model)
    logger.info("  Gemini API Key: %s", "✅ set" if settings.gemini_api_key else "❌ NOT SET")
    logger.info("  Maps API Key: %s", "✅ set" if settings.maps_api_key else "❌ NOT SET")
    logger.info("  Firestore Project: %s", settings.firestore_project_id or "❌ NOT SET (using in-memory)")
    logger.info("  Calendar: %s", "✅ enabled" if settings.google_calendar_enabled else "demo mode")
    logger.info("  CORS Origins: %s", settings.cors_origin_list)
    logger.info("=" * 60)
