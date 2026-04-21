"""
NutriOS — Test Configuration & Shared Fixtures

Provides FastAPI test client, mock services, and demo JWT tokens
for all test files. Uses pytest-asyncio for async test support.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from config import get_settings
from main import app
from middleware.auth import create_access_token


@pytest.fixture(scope="session")
def demo_token() -> str:
    """Generate a demo JWT token for authenticated test requests."""
    return create_access_token(user_id="test_user_001", name="Test User")


@pytest.fixture(scope="session")
def auth_headers(demo_token: str) -> dict:
    """Authorization headers with the demo JWT token."""
    return {"Authorization": f"Bearer {demo_token}"}


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
def settings():
    """Application settings for tests."""
    return get_settings()
