"""
NutriOS — Nudge Router Tests

Tests for the POST /nudge endpoint including:
- Successful nudge generation
- Authentication requirements
- Input validation
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_nudge_success(client: AsyncClient, auth_headers: dict):
    """Test that a valid nudge request returns a personalized nudge."""
    response = await client.post(
        "/nudge",
        json={
            "latitude": 37.7749,
            "longitude": -122.4194,
            "activity_level": "moderate",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "nudge" in data
    assert isinstance(data["nudge"], str)
    assert len(data["nudge"]) > 0
    assert "message" in data
    assert "nearby_places" in data
    assert isinstance(data["nearby_places"], list)
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_nudge_without_auth(client: AsyncClient):
    """Test that nudge endpoint requires authentication."""
    response = await client.post(
        "/nudge",
        json={"latitude": 37.7749, "longitude": -122.4194},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_nudge_invalid_coordinates(client: AsyncClient, auth_headers: dict):
    """Test that invalid coordinates are rejected by Pydantic validation."""
    response = await client.post(
        "/nudge",
        json={"latitude": 999, "longitude": -122.4194},
        headers=auth_headers,
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_nudge_minimal_request(client: AsyncClient, auth_headers: dict):
    """Test nudge with only required fields (no activity_level)."""
    response = await client.post(
        "/nudge",
        json={"latitude": 0.0, "longitude": 0.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "nudge" in data
