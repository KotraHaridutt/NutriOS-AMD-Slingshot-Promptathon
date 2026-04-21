"""
NutriOS — Conversational Food Coach Router

POST /coach — Multi-turn food coaching chat powered by Gemini.
Context window includes user's meal history, goals, and schedule.
Supports both standard JSON responses and SSE streaming.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from middleware.auth import get_current_user_id
from models.schemas import CoachRequest, CoachResponse, ErrorResponse
from services import context, gemini

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Food Coach"])


@router.post(
    "/coach",
    response_model=CoachResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Chat with food coach",
    description=(
        "Multi-turn conversational food coaching powered by Gemini. "
        "The coach has access to your meal history, goals, and today's schedule. "
        "Add `?stream=true` to get Server-Sent Events streaming response."
    ),
)
async def chat_with_coach(
    request: CoachRequest,
    user_id: str = Depends(get_current_user_id),
    stream: bool = Query(
        default=False,
        description="If true, returns a streaming SSE response",
    ),
):
    """
    Chat with the NutriOS food coach.

    The coach has full context about the user: their meal history,
    dietary goals, restrictions, and today's schedule. Advice is
    specific to THIS person, TODAY — never generic.

    Use `stream=true` query param for real-time SSE streaming.
    """
    logger.info("Coach message from user %s: '%s' (stream=%s)",
                user_id, request.message[:50], stream)

    # Aggregate user context for personalization
    user_context = await context.aggregate_coach_context(user_id)

    # Convert conversation history to list of dicts
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.conversation_history
    ]

    if stream:
        # Return SSE streaming response
        return StreamingResponse(
            _stream_response(request.message, history, user_context),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Standard JSON response
    reply = await gemini.chat_coach(
        message=request.message,
        conversation_history=history,
        user_context=user_context,
    )

    return CoachResponse(
        reply=reply,
        message="Coach response generated.",
    )


async def _stream_response(
    message: str,
    history: list,
    user_context: dict,
):
    """
    SSE stream generator for the coach response.
    Yields Server-Sent Events format data.
    """
    try:
        async for chunk in gemini.chat_coach_stream(
            message=message,
            conversation_history=history,
            user_context=user_context,
        ):
            # SSE format: data: <content>\n\n
            data = json.dumps({"text": chunk})
            yield f"data: {data}\n\n"

        # Signal stream end
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        logger.error("SSE stream error: %s", e)
        error_data = json.dumps({"error": "Stream interrupted. Please try again."})
        yield f"data: {error_data}\n\n"
