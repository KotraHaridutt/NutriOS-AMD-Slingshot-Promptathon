"""
NutriOS — Food Logging Router Tests

Tests for:
- POST /log/photo — photo-based meal logging
- POST /log/manual — text-based meal logging
- Authentication and validation
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_manual_log_success(client: AsyncClient, auth_headers: dict):
    """Test manual meal logging with a text description."""
    response = await client.post(
        "/log/manual",
        json={
            "food_description": "Grilled chicken breast with brown rice and steamed broccoli",
            "meal_type": "lunch",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "meal" in data
    meal = data["meal"]
    assert "food_name" in meal
    assert "macros" in meal
    assert meal["source"] == "manual"
    assert "message" in data


@pytest.mark.asyncio
async def test_manual_log_without_auth(client: AsyncClient):
    """Test that manual logging requires authentication."""
    response = await client.post(
        "/log/manual",
        json={"food_description": "A salad", "meal_type": "lunch"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_manual_log_validation(client: AsyncClient, auth_headers: dict):
    """Test input validation — empty description should fail."""
    response = await client.post(
        "/log/manual",
        json={"food_description": "", "meal_type": "lunch"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_manual_log_invalid_meal_type(client: AsyncClient, auth_headers: dict):
    """Test that invalid meal types are rejected."""
    response = await client.post(
        "/log/manual",
        json={"food_description": "A pizza", "meal_type": "midnight_feast"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_photo_log_without_auth(client: AsyncClient):
    """Test that photo logging requires authentication."""
    # Create a minimal fake JPEG
    fake_image = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    response = await client.post(
        "/log/photo",
        files={"photo": ("test.jpg", fake_image, "image/jpeg")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_photo_log_invalid_type(client: AsyncClient, auth_headers: dict):
    """Test that non-image uploads are rejected."""
    fake_file = io.BytesIO(b"not an image")

    response = await client.post(
        "/log/photo",
        files={"photo": ("test.txt", fake_file, "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 400
