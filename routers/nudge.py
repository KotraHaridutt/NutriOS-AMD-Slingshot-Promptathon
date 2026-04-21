"""
NutriOS — Nudge Router

POST /nudge — The core feature. Generates a contextual food nudge
based on the user's schedule, location, activity, and meal history.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from middleware.auth import get_current_user_id
from models.schemas import (
    CalendarEvent,
    ErrorResponse,
    NearbyPlace,
    NudgeRequest,
    NudgeResponse,
)
from services import context, gemini

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Nudge"])


@router.post(
    "/nudge",
    response_model=NudgeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get contextual food nudge",
    description=(
        "Generates a personalized, context-aware food recommendation "
        "based on the user's schedule, location, activity, and meal history. "
        "This is the core NutriOS feature — proactive, not reactive."
    ),
)
async def get_nudge(
    request: NudgeRequest,
    user_id: str = Depends(get_current_user_id),
) -> NudgeResponse:
    """
    Generate a contextual food nudge for the user.

    Flow:
    1. Aggregate context (profile + meals + calendar + places) in parallel
    2. Build dynamic prompt with all context
    3. Call Gemini to generate the nudge
    4. Return nudge with supporting data (nearby places, next event)
    """
    logger.info("Nudge requested by user %s at (%.4f, %.4f)",
                user_id, request.latitude, request.longitude)

    # Step 1: Aggregate all context in parallel
    ctx = await context.aggregate_context(
        user_id=user_id,
        latitude=request.latitude,
        longitude=request.longitude,
        activity_level=request.activity_level,
    )

    # Step 2: Generate nudge with Gemini
    nudge_text = await gemini.generate_nudge(ctx)

    # Step 3: Build response with supporting data
    nearby_places = [
        NearbyPlace(**p)
        for p in (ctx.get("_nearby_places") or [])[:3]
    ]

    events = ctx.get("_events") or []
    next_event = None
    if events:
        next_event = CalendarEvent(
            summary=events[0].get("summary", "Event"),
            start_time=events[0].get("start_time", ""),
            end_time=events[0].get("end_time"),
            minutes_until=events[0].get("minutes_until"),
        )

    return NudgeResponse(
        nudge=nudge_text,
        nearby_places=nearby_places,
        next_event=next_event,
        message="Here's your personalized food nudge!",
    )
