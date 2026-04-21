"""
NutriOS — Gemini AI Service

All Gemini API interactions using the NEW google-genai SDK.
Handles: nudge generation, vision food analysis, chat coaching,
and weekly insights.

SDK: google-genai (NOT the deprecated google-generativeai)
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from google import genai
from google.genai import types

from config import get_settings

logger = logging.getLogger(__name__)

# ── Client Singleton ───────────────────────────────────────────
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please add it to your .env file."
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Gemini client initialized with model: %s", settings.gemini_model)
    return _client


def _get_model_name() -> str:
    """Get the configured model name."""
    return get_settings().gemini_model


# ═══════════════════════════════════════════════════════════════
# NUDGE GENERATION
# ═══════════════════════════════════════════════════════════════

NUDGE_SYSTEM_PROMPT = """You are NutriOS, a personal food intelligence assistant.
You have access to the user's full context below.
Generate ONE specific, actionable food recommendation for right now.
Be direct. Include a nearby place if available. Max 2 sentences.

USER CONTEXT:
- Name: {name}
- Goals: {goals}
- Next calendar event: {next_event} (in {time_until} minutes)
- Location: {location_description}
- Nearby healthy options: {nearby_places}
- Last meal logged: {last_meal} ({hours_since}h ago)
- Today's activity: {activity_summary}
- Weekly pattern: {pattern_summary}
- Dietary restrictions: {dietary_restrictions}

Respond with a nudge that accounts for their upcoming schedule and energy needs.
Keep it conversational, specific, and actionable."""


async def generate_nudge(context: Dict[str, Any]) -> str:
    """
    Generate a contextual food nudge using Gemini.

    Args:
        context: Aggregated user context dict with keys matching
                 the NUDGE_SYSTEM_PROMPT template variables.

    Returns:
        A personalized food recommendation string.
    """
    try:
        client = _get_client()
        prompt = NUDGE_SYSTEM_PROMPT.format(
            name=context.get("name", "there"),
            goals=context.get("goals", "eat healthier"),
            next_event=context.get("next_event", "nothing scheduled"),
            time_until=context.get("time_until", "N/A"),
            location_description=context.get("location_description", "unknown location"),
            nearby_places=context.get("nearby_places", "none found"),
            last_meal=context.get("last_meal", "unknown"),
            hours_since=context.get("hours_since", "unknown"),
            activity_summary=context.get("activity_summary", "not reported"),
            pattern_summary=context.get("pattern_summary", "no data yet"),
            dietary_restrictions=context.get("dietary_restrictions", "none"),
        )

        response = client.models.generate_content(
            model=_get_model_name(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=256,
            ),
        )

        nudge_text = response.text.strip() if response.text else ""
        if not nudge_text:
            nudge_text = "Time for a balanced meal! Consider something with lean protein and vegetables."

        logger.info("Nudge generated successfully")
        return nudge_text

    except Exception as e:
        logger.error("Nudge generation failed: %s", e)
        return "I'm having trouble generating a personalized nudge right now. Try a balanced meal with protein, healthy fats, and vegetables!"


# ═══════════════════════════════════════════════════════════════
# VISION FOOD LOGGING
# ═══════════════════════════════════════════════════════════════

VISION_PROMPT = """Analyze this food image and identify the meal.

Return a JSON object with these exact keys:
{
  "food_name": "Name of the food/dish",
  "description": "Brief description of what you see",
  "meal_type": "breakfast|lunch|dinner|snack",
  "macros": {
    "calories": <number>,
    "protein_g": <number>,
    "carbs_g": <number>,
    "fat_g": <number>,
    "fiber_g": <number or null>
  },
  "confidence": <float 0-1>
}

Be as accurate as possible with macro estimates. Use typical serving sizes.
Return ONLY the JSON object, no additional text."""


async def analyze_food_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """
    Analyze a food photo using Gemini Vision.

    Args:
        image_bytes: Raw bytes of the food image.
        mime_type: MIME type of the image (image/jpeg, image/png, etc.).

    Returns:
        Dict with food_name, description, meal_type, macros, and confidence.
    """
    try:
        client = _get_client()

        response = client.models.generate_content(
            model=_get_model_name(),
            contents=[
                VISION_PROMPT,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=512,
            ),
        )

        raw_text = response.text.strip() if response.text else ""

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]) if len(lines) > 2 else raw_text

        result = json.loads(raw_text)
        logger.info("Food image analyzed: %s (confidence: %.2f)",
                     result.get("food_name", "unknown"),
                     result.get("confidence", 0))
        return result

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini vision response as JSON: %s", e)
        return {
            "food_name": "Unidentified meal",
            "description": "Could not identify the food in the image.",
            "meal_type": "snack",
            "macros": {"calories": 300, "protein_g": 15, "carbs_g": 30, "fat_g": 12, "fiber_g": None},
            "confidence": 0.1,
        }
    except Exception as e:
        logger.error("Vision analysis failed: %s", e)
        raise


# ═══════════════════════════════════════════════════════════════
# MANUAL FOOD ANALYSIS
# ═══════════════════════════════════════════════════════════════

MANUAL_LOG_PROMPT = """The user describes a meal they just ate:

"{food_description}"

Analyze this and return a JSON object with these exact keys:
{{
  "food_name": "Identified food name",
  "description": "Brief description",
  "macros": {{
    "calories": <number>,
    "protein_g": <number>,
    "carbs_g": <number>,
    "fat_g": <number>,
    "fiber_g": <number or null>
  }},
  "confidence": <float 0-1>
}}

Use typical serving sizes. Return ONLY the JSON object."""


async def analyze_food_text(food_description: str) -> Dict[str, Any]:
    """
    Analyze a textual food description using Gemini.

    Args:
        food_description: User's text description of their meal.

    Returns:
        Dict with food_name, macros, and confidence.
    """
    try:
        client = _get_client()
        prompt = MANUAL_LOG_PROMPT.format(food_description=food_description)

        response = client.models.generate_content(
            model=_get_model_name(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=512,
            ),
        )

        raw_text = response.text.strip() if response.text else ""
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]) if len(lines) > 2 else raw_text

        return json.loads(raw_text)

    except json.JSONDecodeError:
        logger.error("Failed to parse manual food analysis JSON")
        return {
            "food_name": food_description[:50],
            "description": food_description,
            "macros": {"calories": 400, "protein_g": 20, "carbs_g": 40, "fat_g": 15, "fiber_g": None},
            "confidence": 0.2,
        }
    except Exception as e:
        logger.error("Manual food analysis failed: %s", e)
        raise


# ═══════════════════════════════════════════════════════════════
# CONVERSATIONAL FOOD COACH
# ═══════════════════════════════════════════════════════════════

COACH_SYSTEM_PROMPT = """You are NutriOS Coach — a friendly, expert food and nutrition coach.
You give personalized advice based on the user's context below.

USER CONTEXT:
- Name: {name}
- Goal: {goals}
- Dietary restrictions: {dietary_restrictions}
- Recent meals (last 7 days summary): {recent_meals_summary}
- Today's schedule: {todays_schedule}
- Current habit score: {habit_score}/100

Rules:
1. Give advice specific to THIS person's context — never generic.
2. Reference their actual meals and schedule.
3. Be encouraging but honest about areas for improvement.
4. Keep responses concise (2-4 sentences unless they ask for detail).
5. If they ask about food, provide macro estimates."""


async def chat_coach(
    message: str,
    conversation_history: List[Dict[str, str]],
    user_context: Dict[str, Any],
) -> str:
    """
    Multi-turn food coaching chat using Gemini.

    Args:
        message: The user's current message.
        conversation_history: List of previous {role, content} dicts.
        user_context: Aggregated user context for personalization.

    Returns:
        The coach's response string.
    """
    try:
        client = _get_client()

        system_prompt = COACH_SYSTEM_PROMPT.format(
            name=user_context.get("name", "there"),
            goals=user_context.get("goals", "eat healthier"),
            dietary_restrictions=user_context.get("dietary_restrictions", "none"),
            recent_meals_summary=user_context.get("recent_meals_summary", "no data"),
            todays_schedule=user_context.get("todays_schedule", "no schedule data"),
            habit_score=user_context.get("habit_score", "N/A"),
        )

        # Build the full prompt with conversation history
        full_contents = [system_prompt]
        for msg in conversation_history[-10:]:  # Keep last 10 messages for context window
            full_contents.append(f"{msg['role'].upper()}: {msg['content']}")
        full_contents.append(f"USER: {message}")

        response = client.models.generate_content(
            model=_get_model_name(),
            contents="\n\n".join(full_contents),
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=1024,
            ),
        )

        reply = response.text.strip() if response.text else ""
        if not reply:
            reply = "I'm here to help with your nutrition! Could you tell me more about what you'd like advice on?"

        return reply

    except Exception as e:
        logger.error("Coach chat failed: %s", e)
        return "I'm having a brief hiccup. Could you try asking again? I'm here to help with your nutrition goals!"


# ═══════════════════════════════════════════════════════════════
# STREAMING COACH (for SSE)
# ═══════════════════════════════════════════════════════════════

async def chat_coach_stream(
    message: str,
    conversation_history: List[Dict[str, str]],
    user_context: Dict[str, Any],
) -> AsyncIterator[str]:
    """
    Streaming version of the food coaching chat.
    Yields text chunks as they arrive from Gemini.

    Args:
        message: The user's current message.
        conversation_history: Previous conversation messages.
        user_context: Aggregated user context.

    Yields:
        Text chunks from the coach's response.
    """
    try:
        client = _get_client()

        system_prompt = COACH_SYSTEM_PROMPT.format(
            name=user_context.get("name", "there"),
            goals=user_context.get("goals", "eat healthier"),
            dietary_restrictions=user_context.get("dietary_restrictions", "none"),
            recent_meals_summary=user_context.get("recent_meals_summary", "no data"),
            todays_schedule=user_context.get("todays_schedule", "no schedule data"),
            habit_score=user_context.get("habit_score", "N/A"),
        )

        full_contents = [system_prompt]
        for msg in conversation_history[-10:]:
            full_contents.append(f"{msg['role'].upper()}: {msg['content']}")
        full_contents.append(f"USER: {message}")

        response = client.models.generate_content_stream(
            model=_get_model_name(),
            contents="\n\n".join(full_contents),
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=1024,
            ),
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        logger.error("Streaming coach failed: %s", e)
        yield "I'm having a brief hiccup. Please try again!"


# ═══════════════════════════════════════════════════════════════
# WEEKLY INSIGHTS
# ═══════════════════════════════════════════════════════════════

INSIGHTS_PROMPT = """Analyze this user's weekly nutrition data and generate 3-5 specific, actionable insights.

User: {name}
Goal: {goals}
Weekly Summary:
{weekly_summary}

Habit Score: {habit_score}/100
- Consistency: {consistency}/100
- Variety: {variety}/100
- Timing: {timing}/100

Generate insights as a JSON array of strings.
Example: ["You ate breakfast consistently at 8am — great routine!", "Consider adding more protein to your lunches"]

Return ONLY the JSON array."""


async def generate_weekly_insights(
    user_context: Dict[str, Any],
    weekly_summary: str,
    habit_scores: Dict[str, float],
) -> List[str]:
    """
    Generate AI-powered weekly nutrition insights.

    Args:
        user_context: User profile context.
        weekly_summary: Text summary of the week's meals.
        habit_scores: Dict with overall, consistency, variety, timing scores.

    Returns:
        List of insight strings.
    """
    try:
        client = _get_client()
        prompt = INSIGHTS_PROMPT.format(
            name=user_context.get("name", "User"),
            goals=user_context.get("goals", "eat healthier"),
            weekly_summary=weekly_summary,
            habit_score=habit_scores.get("overall", 0),
            consistency=habit_scores.get("consistency", 0),
            variety=habit_scores.get("variety", 0),
            timing=habit_scores.get("timing", 0),
        )

        response = client.models.generate_content(
            model=_get_model_name(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.6,
                max_output_tokens=512,
            ),
        )

        raw_text = response.text.strip() if response.text else "[]"
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]) if len(lines) > 2 else raw_text

        insights = json.loads(raw_text)
        return insights if isinstance(insights, list) else []

    except Exception as e:
        logger.error("Weekly insights generation failed: %s", e)
        return [
            "Keep logging your meals consistently for better insights!",
            "Try to eat at regular times each day.",
            "Aim for a variety of food groups across the week.",
        ]
