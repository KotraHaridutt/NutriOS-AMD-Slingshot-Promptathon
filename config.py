"""
NutriOS — Centralized Application Configuration

Uses pydantic-settings for type-safe environment variable loading
with validation, defaults, and .env file support.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemini AI ──────────────────────────────────────────────
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model name (gemini-2.0-flash or gemini-2.5-flash)",
    )

    # ── Google Maps ────────────────────────────────────────────
    maps_api_key: str = Field(default="", description="Google Maps Platform API key")

    # ── Firestore ──────────────────────────────────────────────
    firestore_project_id: str = Field(default="", description="GCP project ID for Firestore")
    google_application_credentials: str = Field(
        default="", description="Path to GCP service account JSON"
    )

    # ── Google Calendar ────────────────────────────────────────
    google_calendar_enabled: bool = Field(
        default=False,
        description="Enable real Google Calendar API (requires OAuth2 setup)",
    )

    # ── Authentication ─────────────────────────────────────────
    jwt_secret: str = Field(
        default="nutrios-dev-secret-change-in-production",
        description="Secret key for signing JWT tokens",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expiry_hours: int = Field(default=24, description="JWT token expiry in hours")

    # ── Application ────────────────────────────────────────────
    port: int = Field(default=8080, description="Server port")
    environment: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="info", description="Logging level")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Cached singleton for application settings.
    Call this function to access settings anywhere in the app.
    """
    return Settings()
