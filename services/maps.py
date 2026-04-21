"""
NutriOS — Google Maps Places Service

Uses the Places API (New) v2 via REST + httpx for async
nearby healthy restaurant lookup.

Endpoint: https://places.googleapis.com/v1/places:searchNearby
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

# Places API v2 endpoint
PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Food-related place types for healthy options
HEALTHY_PLACE_TYPES = [
    "restaurant",
    "cafe",
    "meal_delivery",
    "meal_takeaway",
    "health",
]

# Fields to request (controls cost — only request what we need)
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.types",
    "places.location",
])


async def get_nearby_healthy_places(
    latitude: float,
    longitude: float,
    radius_meters: float = 800.0,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for nearby healthy food places using Google Places API v2.

    Args:
        latitude: User's current latitude.
        longitude: User's current longitude.
        radius_meters: Search radius in meters (default 800m).
        max_results: Maximum number of places to return.

    Returns:
        List of dicts with name, address, rating, distance, and place_id.
    """
    settings = get_settings()

    if not settings.maps_api_key:
        logger.warning("MAPS_API_KEY not set — returning demo places")
        return _get_demo_places()

    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.maps_api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        body = {
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": radius_meters,
                }
            },
            "includedTypes": HEALTHY_PLACE_TYPES,
            "maxResultCount": max_results,
            "rankPreference": "DISTANCE",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                PLACES_NEARBY_URL,
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        places = []
        for place in data.get("places", []):
            place_location = place.get("location", {})
            distance = _haversine_distance(
                latitude, longitude,
                place_location.get("latitude", 0),
                place_location.get("longitude", 0),
            )

            display_name = place.get("displayName", {})
            places.append({
                "name": display_name.get("text", "Unknown"),
                "address": place.get("formattedAddress", ""),
                "rating": place.get("rating"),
                "distance_meters": round(distance, 1),
                "place_id": place.get("id", ""),
            })

        # Sort by distance
        places.sort(key=lambda p: p.get("distance_meters", float("inf")))
        logger.info("Found %d nearby places at (%.4f, %.4f)", len(places), latitude, longitude)
        return places

    except httpx.HTTPStatusError as e:
        logger.error("Places API HTTP error: %s — %s", e.response.status_code, e.response.text)
        return _get_demo_places()
    except Exception as e:
        logger.error("Places API request failed: %s", e)
        return _get_demo_places()


def format_places_for_prompt(places: List[Dict[str, Any]]) -> str:
    """
    Format nearby places into a human-readable string for the Gemini prompt.

    Args:
        places: List of place dicts from get_nearby_healthy_places().

    Returns:
        Formatted string for inclusion in the nudge prompt.
    """
    if not places:
        return "No nearby options found"

    lines = []
    for p in places[:5]:
        rating_str = f" (★{p['rating']})" if p.get("rating") else ""
        distance_str = f" ~{p['distance_meters']:.0f}m away" if p.get("distance_meters") else ""
        lines.append(f"• {p['name']}{rating_str}{distance_str}")

    return "\n".join(lines)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: First point coordinates.
        lat2, lon2: Second point coordinates.

    Returns:
        Distance in meters.
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371000  # Earth radius in meters

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def _get_demo_places() -> List[Dict[str, Any]]:
    """Return demo places when Maps API is not configured."""
    return [
        {
            "name": "Green Bowl Salads",
            "address": "123 Health St",
            "rating": 4.5,
            "distance_meters": 150.0,
            "place_id": "demo_place_1",
        },
        {
            "name": "Protein Kitchen",
            "address": "456 Fitness Ave",
            "rating": 4.3,
            "distance_meters": 300.0,
            "place_id": "demo_place_2",
        },
        {
            "name": "Fresh Bites Café",
            "address": "789 Wellness Blvd",
            "rating": 4.7,
            "distance_meters": 500.0,
            "place_id": "demo_place_3",
        },
    ]
