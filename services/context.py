"""
NutriOS — Context Aggregator

Fetches all user context in parallel using asyncio.gather().
Combines: profile, recent meals, calendar events, nearby places.
Builds the context dict consumed by Gemini prompts.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services import firestore_svc, maps, calendar_svc

logger = logging.getLogger(__name__)


async def aggregate_context(
    user_id: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    activity_level: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate all user context for Gemini prompt assembly.
    All external API calls are made in PARALLEL via asyncio.gather().

    Args:
        user_id: The unique user identifier.
        latitude: User's current latitude (optional).
        longitude: User's current longitude (optional).
        activity_level: User-reported activity level (optional).

    Returns:
        Comprehensive context dict ready for Gemini prompt templates.
    """
    # ── Parallel fetch all context sources ─────────────────────
    profile_task = firestore_svc.get_user_profile(user_id)
    meals_task = firestore_svc.get_recent_meals(user_id, days=7)
    events_task = calendar_svc.get_upcoming_events(user_id)

    # Only fetch places if we have location data
    if latitude is not None and longitude is not None:
        places_task = maps.get_nearby_healthy_places(latitude, longitude)
    else:
        places_task = _empty_list()

    # Execute all in parallel
    profile, recent_meals, events, nearby_places = await asyncio.gather(
        profile_task,
        meals_task,
        events_task,
        places_task,
        return_exceptions=True,
    )

    # Handle any exceptions from parallel tasks gracefully
    if isinstance(profile, Exception):
        logger.error("Profile fetch failed: %s", profile)
        profile = None
    if isinstance(recent_meals, Exception):
        logger.error("Meals fetch failed: %s", recent_meals)
        recent_meals = []
    if isinstance(events, Exception):
        logger.error("Calendar fetch failed: %s", events)
        events = []
    if isinstance(nearby_places, Exception):
        logger.error("Places fetch failed: %s", nearby_places)
        nearby_places = []

    # ── Build context dict ─────────────────────────────────────
    context = _build_context(
        profile=profile,
        recent_meals=recent_meals,
        events=events,
        nearby_places=nearby_places,
        activity_level=activity_level,
    )

    logger.info(
        "Context aggregated for user %s — %d meals, %d events, %d places",
        user_id,
        len(recent_meals) if isinstance(recent_meals, list) else 0,
        len(events) if isinstance(events, list) else 0,
        len(nearby_places) if isinstance(nearby_places, list) else 0,
    )

    return context


async def aggregate_coach_context(user_id: str) -> Dict[str, Any]:
    """
    Aggregate context specifically for the chat coach.
    Lighter-weight than full aggregation — no location or places.

    Args:
        user_id: The unique user identifier.

    Returns:
        Context dict for coach prompt assembly.
    """
    profile, recent_meals, events = await asyncio.gather(
        firestore_svc.get_user_profile(user_id),
        firestore_svc.get_recent_meals(user_id, days=7),
        calendar_svc.get_upcoming_events(user_id),
        return_exceptions=True,
    )

    if isinstance(profile, Exception):
        profile = None
    if isinstance(recent_meals, Exception):
        recent_meals = []
    if isinstance(events, Exception):
        events = []

    # Summarize recent meals for prompt
    meals_summary = _summarize_meals(recent_meals)
    schedule_summary = _summarize_schedule(events)
    habit_score = _calculate_simple_habit_score(recent_meals)

    return {
        "name": profile.get("name", "there") if profile else "there",
        "goals": profile.get("goal", "eat_healthier") if profile else "eat_healthier",
        "dietary_restrictions": ", ".join(
            profile.get("dietary_restrictions", [])
        ) if profile else "none",
        "recent_meals_summary": meals_summary,
        "todays_schedule": schedule_summary,
        "habit_score": str(round(habit_score)),
    }


def _build_context(
    profile: Optional[Dict],
    recent_meals: list,
    events: list,
    nearby_places: list,
    activity_level: Optional[str],
) -> Dict[str, Any]:
    """Build the full context dict for nudge generation."""
    # Extract profile info
    name = profile.get("name", "there") if profile else "there"
    goals = profile.get("goal", "eat_healthier") if profile else "eat_healthier"
    dietary_restrictions = ", ".join(
        profile.get("dietary_restrictions", [])
    ) if profile else "none"

    # Format calendar events
    next_event, time_until = calendar_svc.format_events_for_prompt(events)

    # Format nearby places
    nearby_str = maps.format_places_for_prompt(nearby_places)

    # Last meal info
    last_meal_str, hours_since = _format_last_meal(recent_meals)

    # Activity summary
    activity_summary = activity_level or "not reported"

    # Weekly pattern
    pattern_summary = _summarize_meals(recent_meals)

    # Location description
    location_desc = "near your current location" if nearby_places else "location unknown"

    return {
        "name": name,
        "goals": goals,
        "dietary_restrictions": dietary_restrictions,
        "next_event": next_event,
        "time_until": time_until,
        "location_description": location_desc,
        "nearby_places": nearby_str,
        "last_meal": last_meal_str,
        "hours_since": hours_since,
        "activity_summary": activity_summary,
        "pattern_summary": pattern_summary,
        # Raw data for downstream use
        "_profile": profile,
        "_recent_meals": recent_meals,
        "_events": events,
        "_nearby_places": nearby_places,
    }


def _format_last_meal(meals: list) -> tuple[str, str]:
    """Format the last meal info for the prompt."""
    if not meals:
        return "no meals logged recently", "unknown"

    last = meals[0]  # Already sorted most-recent first
    food_name = last.get("food_name", "a meal")

    logged_at = last.get("logged_at", "")
    if logged_at:
        try:
            meal_time = datetime.fromisoformat(logged_at)
            now = datetime.now(timezone.utc)
            # Handle naive datetime
            if meal_time.tzinfo is None:
                meal_time = meal_time.replace(tzinfo=timezone.utc)
            hours_ago = (now - meal_time).total_seconds() / 3600
            return food_name, f"{hours_ago:.1f}"
        except (ValueError, TypeError):
            pass

    return food_name, "unknown"


def _summarize_meals(meals: list) -> str:
    """Create a text summary of recent meals for prompts."""
    if not meals:
        return "No meals logged in the past week"

    # Group by day
    days_with_meals = set()
    total_cals = 0.0
    food_names = []

    for meal in meals:
        logged_at = meal.get("logged_at", "")[:10]  # YYYY-MM-DD
        if logged_at:
            days_with_meals.add(logged_at)

        macros = meal.get("macros", {})
        if isinstance(macros, dict):
            total_cals += macros.get("calories", 0)

        food_name = meal.get("food_name", "")
        if food_name:
            food_names.append(food_name)

    avg_cals = total_cals / len(days_with_meals) if days_with_meals else 0
    unique_foods = len(set(food_names))

    return (
        f"{len(meals)} meals logged across {len(days_with_meals)} days. "
        f"Avg ~{avg_cals:.0f} cal/day. "
        f"{unique_foods} unique foods. "
        f"Recent: {', '.join(food_names[:5])}"
    )


def _summarize_schedule(events: list) -> str:
    """Summarize today's schedule for coach context."""
    if not events:
        return "No upcoming events"

    summaries = []
    for event in events[:3]:
        summary = event.get("summary", "Event")
        minutes = event.get("minutes_until")
        if minutes is not None and minutes < 60:
            summaries.append(f"{summary} (in {minutes}min)")
        elif minutes is not None:
            hours = minutes / 60
            summaries.append(f"{summary} (in {hours:.1f}h)")
        else:
            summaries.append(summary)

    return ", ".join(summaries)


def _calculate_simple_habit_score(meals: list) -> float:
    """
    Calculate a simple habit score for coach context.
    Full scoring is in the report endpoint.
    """
    if not meals:
        return 0.0

    # Simple heuristic based on logging frequency
    days_with_meals = len(set(m.get("logged_at", "")[:10] for m in meals if m.get("logged_at")))
    unique_foods = len(set(m.get("food_name", "") for m in meals if m.get("food_name")))

    consistency = min(days_with_meals / 7 * 100, 100)
    variety = min(unique_foods / 10 * 100, 100)

    return (consistency * 0.6 + variety * 0.4)


async def _empty_list() -> list:
    """Async helper that returns an empty list."""
    return []
