"""
NutriOS — Firestore Service

Async Firestore operations for user profiles, meal logs,
and all persistent data. Uses google-cloud-firestore AsyncClient.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config import get_settings

logger = logging.getLogger(__name__)

# ── Firestore Client Singleton ─────────────────────────────────
_db = None


def _get_db():
    """Lazy-initialize Firestore async client."""
    global _db
    if _db is None:
        settings = get_settings()
        if settings.firestore_project_id:
            try:
                from google.cloud.firestore_v1 import AsyncClient
                _db = AsyncClient(project=settings.firestore_project_id)
                logger.info("Firestore AsyncClient initialized for project: %s", settings.firestore_project_id)
            except Exception as e:
                logger.warning("Firestore unavailable, using in-memory fallback: %s", e)
                _db = _InMemoryDB()
        else:
            logger.warning("FIRESTORE_PROJECT_ID not set — using in-memory fallback DB")
            _db = _InMemoryDB()
    return _db


class _InMemoryDB:
    """
    In-memory mock database for development/demo mode.
    Mimics the Firestore document structure so the rest of the app
    works identically without a real Firestore instance.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        logger.info("In-memory database initialized (demo mode)")

    def collection(self, name: str) -> "_InMemoryCollection":
        return _InMemoryCollection(self._store, name)


class _InMemoryCollection:
    """Mock Firestore collection."""

    def __init__(self, store: Dict, name: str) -> None:
        self._store = store
        self._name = name
        self._filters: List = []

    def document(self, doc_id: str) -> "_InMemoryDocument":
        return _InMemoryDocument(self._store, f"{self._name}/{doc_id}")

    def where(self, field: str = "", op_string: str = "", value: Any = None, **kwargs) -> "_InMemoryCollection":
        """Mock where clause — stores filter but returns self for chaining."""
        self._filters.append((field or kwargs.get("filter", ""), op_string, value))
        return self

    def order_by(self, field: str, **kwargs) -> "_InMemoryCollection":
        return self

    def limit(self, count: int) -> "_InMemoryCollection":
        return self

    async def get(self) -> List["_InMemoryDocument"]:
        """Return all docs in the collection matching the path prefix."""
        results = []
        prefix = f"{self._name}/"
        for key, val in self._store.items():
            if key.startswith(prefix):
                doc = _InMemoryDocument(self._store, key)
                doc._data = val
                doc._exists = True
                results.append(doc)
        return results

    async def add(self, data: Dict[str, Any]) -> tuple:
        doc_id = str(uuid4())
        path = f"{self._name}/{doc_id}"
        self._store[path] = data
        return None, _InMemoryDocument(self._store, path)


class _InMemoryDocument:
    """Mock Firestore document."""

    def __init__(self, store: Dict, path: str) -> None:
        self._store = store
        self._path = path
        self._data: Optional[Dict] = None
        self._exists: bool = False

    @property
    def id(self) -> str:
        return self._path.split("/")[-1]

    @property
    def exists(self) -> bool:
        return self._exists or self._path in self._store

    def to_dict(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        return self._store.get(self._path, {})

    def collection(self, name: str) -> _InMemoryCollection:
        return _InMemoryCollection(self._store, f"{self._path}/{name}")

    async def get(self) -> "_InMemoryDocument":
        if self._path in self._store:
            self._data = self._store[self._path]
            self._exists = True
        return self

    async def set(self, data: Dict[str, Any], merge: bool = False) -> None:
        if merge and self._path in self._store:
            self._store[self._path].update(data)
        else:
            self._store[self._path] = data

    async def update(self, data: Dict[str, Any]) -> None:
        if self._path in self._store:
            self._store[self._path].update(data)
        else:
            self._store[self._path] = data


# ═══════════════════════════════════════════════════════════════
# PUBLIC SERVICE FUNCTIONS
# ═══════════════════════════════════════════════════════════════


async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user profile from Firestore.

    Args:
        user_id: The unique user identifier.

    Returns:
        User profile dict or None if not found.
    """
    try:
        db = _get_db()
        doc = await db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error("Failed to fetch user profile for %s: %s", user_id, e)
        return None


async def create_or_update_profile(user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create or update a user profile in Firestore.

    Args:
        user_id: The unique user identifier.
        profile_data: Profile fields to set/update.

    Returns:
        The updated profile data.
    """
    try:
        db = _get_db()
        profile_data["updated_at"] = datetime.utcnow().isoformat()
        if "created_at" not in profile_data:
            profile_data["created_at"] = profile_data["updated_at"]
        await db.collection("users").document(user_id).set(profile_data, merge=True)
        logger.info("Profile updated for user %s", user_id)
        return profile_data
    except Exception as e:
        logger.error("Failed to update profile for %s: %s", user_id, e)
        raise


async def log_meal(user_id: str, meal_data: Dict[str, Any]) -> str:
    """
    Log a meal entry to Firestore.

    Document path: users/{uid}/meals/{meal_id}

    Args:
        user_id: The unique user identifier.
        meal_data: Meal entry data including food name, macros, etc.

    Returns:
        The generated meal_id.
    """
    try:
        db = _get_db()
        meal_id = str(uuid4())
        meal_data["meal_id"] = meal_id
        meal_data["logged_at"] = meal_data.get("logged_at", datetime.utcnow().isoformat())

        await (
            db.collection("users")
            .document(user_id)
            .collection("meals")
            .document(meal_id)
            .set(meal_data)
        )
        logger.info("Meal %s logged for user %s", meal_id, user_id)
        return meal_id
    except Exception as e:
        logger.error("Failed to log meal for %s: %s", user_id, e)
        raise


def log_meal_fire_and_forget(user_id: str, meal_data: Dict[str, Any]) -> None:
    """
    Log a meal asynchronously in a fire-and-forget manner.
    Non-blocking — errors are logged but don't propagate.
    """
    async def _write():
        try:
            await log_meal(user_id, meal_data)
        except Exception as e:
            logger.error("Fire-and-forget meal log failed: %s", e)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_write())
    except RuntimeError:
        logger.warning("No running event loop for fire-and-forget write")


async def get_recent_meals(
    user_id: str,
    days: int = 7,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetch recent meal logs for a user.

    Args:
        user_id: The unique user identifier.
        days: Number of days to look back.
        limit: Maximum number of meals to return.

    Returns:
        List of meal dicts, most recent first.
    """
    try:
        db = _get_db()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        meals_ref = (
            db.collection("users")
            .document(user_id)
            .collection("meals")
        )

        docs = await meals_ref.get()
        meals = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("logged_at", "") >= cutoff:
                meals.append(data)

        # Sort by logged_at descending
        meals.sort(key=lambda m: m.get("logged_at", ""), reverse=True)
        return meals[:limit]
    except Exception as e:
        logger.error("Failed to fetch recent meals for %s: %s", user_id, e)
        return []


async def get_meals_for_period(
    user_id: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    Fetch all meals within a date range.

    Args:
        user_id: The unique user identifier.
        start_date: Start date (ISO 8601).
        end_date: End date (ISO 8601).

    Returns:
        List of meal dicts within the period.
    """
    try:
        db = _get_db()
        meals_ref = (
            db.collection("users")
            .document(user_id)
            .collection("meals")
        )

        docs = await meals_ref.get()
        meals = []
        for doc in docs:
            data = doc.to_dict()
            logged = data.get("logged_at", "")
            if start_date <= logged <= end_date:
                meals.append(data)

        meals.sort(key=lambda m: m.get("logged_at", ""))
        return meals
    except Exception as e:
        logger.error("Failed to fetch meals for period: %s", e)
        return []


async def get_last_meal(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recently logged meal for a user.

    Args:
        user_id: The unique user identifier.

    Returns:
        Most recent meal dict or None.
    """
    meals = await get_recent_meals(user_id, days=3, limit=1)
    return meals[0] if meals else None
