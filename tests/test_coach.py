"""
NutriOS — Coach Router Tests

Tests for the POST /coach endpoint including:
- Successful coach chat
- Multi-turn conversation
- Authentication requirements
- Streaming not tested here (requires SSE client)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_coach_success(client: AsyncClient, auth_headers: dict):
    """Test a basic coach chat message."""
    response = await client.post(
        "/coach",
        json={
            "message": "What should I eat for lunch today?",
            "conversation_history": [],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0
    assert "message" in data


@pytest.mark.asyncio
async def test_coach_with_history(client: AsyncClient, auth_headers: dict):
    """Test multi-turn conversation with history."""
    response = await client.post(
        "/coach",
        json={
            "message": "What about for a post-workout snack?",
            "conversation_history": [
                {"role": "user", "content": "What should I eat for lunch?"},
                {"role": "assistant", "content": "Try a grilled chicken salad with quinoa!"},
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data


@pytest.mark.asyncio
async def test_coach_without_auth(client: AsyncClient):
    """Test that coach endpoint requires authentication."""
    response = await client.post(
        "/coach",
        json={"message": "Hello", "conversation_history": []},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_coach_empty_message(client: AsyncClient, auth_headers: dict):
    """Test that empty messages are rejected by validation."""
    response = await client.post(
        "/coach",
        json={"message": "", "conversation_history": []},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Test the health check endpoint (no auth required)."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "nutrios"


@pytest.mark.asyncio
async def test_demo_token_endpoint(client: AsyncClient):
    """Test the demo token generation endpoint."""
    response = await client.post(
        "/auth/demo-token",
        params={"user_id": "test_user", "name": "Tester"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
