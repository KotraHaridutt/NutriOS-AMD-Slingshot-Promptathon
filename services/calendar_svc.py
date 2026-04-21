"""
NutriOS — Google Calendar Service

Fetches upcoming events from Google Calendar to provide
schedule-aware food recommendations.

Supports:
- Real Calendar API via service account (requires GOOGLE_CALENDAR_ENABLED=true)
- Demo mode with realistic mock events (default)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)


async def get_upcoming_events(
    user_id: str,
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    """
    Fetch the user's upcoming calendar events.

    In demo mode (default), returns realistic mock events.
    With real Calendar API enabled, fetches from Google Calendar.

    Args:
        user_id: The user's identifier.
        max_results: Maximum number of events to return.

    Returns:
        List of event dicts with summary, start_time, end_time, minutes_until.
    """
    settings = get_settings()

    if settings.google_calendar_enabled:
        return await _fetch_real_events(user_id, max_results)
    else:
        return _get_demo_events()


async def _fetch_real_events(user_id: str, max_results: int) -> List[Dict[str, Any]]:
    """
    Fetch events from the real Google Calendar API.
    Uses google-api-python-client in a thread executor (it's synchronous).

    Args:
        user_id: The user's identifier (used as calendar ID or email).
        max_results: Maximum number of events.

    Returns:
        List of event dicts.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        def _sync_fetch() -> List[Dict[str, Any]]:
            settings = get_settings()
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials,
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )

            # For domain-wide delegation, impersonate the user
            delegated_credentials = credentials.with_subject(user_id)

            service = build("calendar", "v3", credentials=delegated_credentials)
            now = datetime.utcnow().isoformat() + "Z"

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = []
            for event in events_result.get("items", []):
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event.get("end", {}).get("dateTime")

                # Calculate minutes until event
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    minutes_until = int((start_dt - now_dt).total_seconds() / 60)
                except (ValueError, TypeError):
                    minutes_until = None

                events.append({
                    "summary": event.get("summary", "Busy"),
                    "start_time": start,
                    "end_time": end,
                    "minutes_until": minutes_until,
                })

            return events

        # Run synchronous Google API call in thread pool
        events = await asyncio.to_thread(_sync_fetch)
        logger.info("Fetched %d real calendar events for %s", len(events), user_id)
        return events

    except Exception as e:
        logger.error("Calendar API fetch failed for %s: %s", user_id, e)
        return _get_demo_events()


def _get_demo_events() -> List[Dict[str, Any]]:
    """
    Generate realistic demo calendar events based on current time.
    Events are time-aware so nudges feel authentic.
    """
    now = datetime.now(timezone.utc)
    hour = now.hour

    events = []

    if hour < 12:
        # Morning — show afternoon events
        events.append({
            "summary": "Team Standup",
            "start_time": (now + timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=1, minutes=30)).isoformat(),
            "minutes_until": 60,
        })
        events.append({
            "summary": "Lunch with Sarah",
            "start_time": (now + timedelta(hours=3)).isoformat(),
            "end_time": (now + timedelta(hours=4)).isoformat(),
            "minutes_until": 180,
        })
    elif hour < 17:
        # Afternoon — show evening events
        events.append({
            "summary": "Project Review",
            "start_time": (now + timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "minutes_until": 60,
        })
        events.append({
            "summary": "Gym Session",
            "start_time": (now + timedelta(hours=3)).isoformat(),
            "end_time": (now + timedelta(hours=4)).isoformat(),
            "minutes_until": 180,
        })
    else:
        # Evening — show next morning events
        events.append({
            "summary": "Morning Run",
            "start_time": (now + timedelta(hours=12)).isoformat(),
            "end_time": (now + timedelta(hours=13)).isoformat(),
            "minutes_until": 720,
        })
        events.append({
            "summary": "Breakfast Meeting",
            "start_time": (now + timedelta(hours=14)).isoformat(),
            "end_time": (now + timedelta(hours=15)).isoformat(),
            "minutes_until": 840,
        })

    logger.info("Returning %d demo calendar events", len(events))
    return events


def format_events_for_prompt(events: List[Dict[str, Any]]) -> tuple[str, str]:
    """
    Format calendar events for inclusion in the Gemini prompt.

    Args:
        events: List of event dicts.

    Returns:
        Tuple of (next_event_description, minutes_until_string).
    """
    if not events:
        return "Nothing scheduled", "N/A"

    next_event = events[0]
    summary = next_event.get("summary", "Busy")
    minutes = next_event.get("minutes_until")
    time_str = str(minutes) if minutes is not None else "N/A"

    return summary, time_str
