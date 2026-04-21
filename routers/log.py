"""
NutriOS — Food Logging Router

POST /log/photo  — Upload meal photo → Gemini Vision auto-identifies + logs
POST /log/manual — Log meal by text description → Gemini estimates macros
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from middleware.auth import get_current_user_id
from models.schemas import (
    ErrorResponse,
    Macros,
    ManualLogRequest,
    ManualLogResponse,
    MealLogEntry,
    MealType,
    PhotoLogResponse,
)
from services import firestore_svc, gemini

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/log", tags=["Food Logging"])

# Max image size: 10 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# Accepted image MIME types
ACCEPTED_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/heic": "image/heic",
    "image/heif": "image/heif",
}


@router.post(
    "/photo",
    response_model=PhotoLogResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        413: {"model": ErrorResponse, "description": "Image too large"},
    },
    summary="Log meal from photo",
    description=(
        "Upload a photo of your meal. Gemini Vision identifies the food, "
        "estimates macronutrients, and logs it automatically. No manual entry needed."
    ),
)
async def log_photo(
    photo: UploadFile = File(
        ..., description="Meal photo (JPEG, PNG, or WebP, max 10MB)"
    ),
    user_id: str = Depends(get_current_user_id),
) -> PhotoLogResponse:
    """
    Analyze a food photo with Gemini Vision and log the meal.

    Flow:
    1. Validate the uploaded image (type, size)
    2. Read image bytes
    3. Send to Gemini Vision for analysis
    4. Save meal entry to Firestore
    5. Return the identified meal with macros
    """
    # Validate MIME type
    content_type = photo.content_type or ""
    mime_type = ACCEPTED_TYPES.get(content_type)
    if not mime_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image type: {content_type}. Accepted: {', '.join(ACCEPTED_TYPES.keys())}",
        )

    # Read and validate size
    image_bytes = await photo.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image too large ({len(image_bytes)} bytes). Maximum: {MAX_IMAGE_SIZE} bytes.",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image file.",
        )

    logger.info("Photo log requested by user %s — %d bytes, type %s",
                user_id, len(image_bytes), mime_type)

    # Analyze with Gemini Vision
    analysis = await gemini.analyze_food_image(image_bytes, mime_type)

    # Build meal entry
    macros_data = analysis.get("macros", {})
    meal = MealLogEntry(
        food_name=analysis.get("food_name", "Unidentified food"),
        description=analysis.get("description"),
        meal_type=_safe_meal_type(analysis.get("meal_type", "snack")),
        macros=Macros(
            calories=macros_data.get("calories", 0),
            protein_g=macros_data.get("protein_g", 0),
            carbs_g=macros_data.get("carbs_g", 0),
            fat_g=macros_data.get("fat_g", 0),
            fiber_g=macros_data.get("fiber_g"),
        ),
        source="photo",
        confidence=analysis.get("confidence"),
    )

    # Log to Firestore (fire-and-forget for speed)
    firestore_svc.log_meal_fire_and_forget(user_id, meal.model_dump())

    return PhotoLogResponse(
        meal=meal,
        message=f"Identified: {meal.food_name}. Meal logged successfully!",
    )


@router.post(
    "/manual",
    response_model=ManualLogResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Log meal manually",
    description=(
        "Describe your meal in text. Gemini analyzes the description, "
        "estimates macronutrients, and logs it."
    ),
)
async def log_manual(
    request: ManualLogRequest,
    user_id: str = Depends(get_current_user_id),
) -> ManualLogResponse:
    """
    Log a meal from text description.

    Flow:
    1. Send text description to Gemini for analysis
    2. Build meal entry with estimated macros
    3. Save to Firestore
    4. Return the analyzed meal
    """
    logger.info("Manual log by user %s: '%s'", user_id, request.food_description[:50])

    # Analyze with Gemini
    analysis = await gemini.analyze_food_text(request.food_description)

    # Build meal entry
    macros_data = analysis.get("macros", {})
    meal = MealLogEntry(
        food_name=analysis.get("food_name", request.food_description[:50]),
        description=request.food_description,
        meal_type=request.meal_type,
        macros=Macros(
            calories=macros_data.get("calories", 0),
            protein_g=macros_data.get("protein_g", 0),
            carbs_g=macros_data.get("carbs_g", 0),
            fat_g=macros_data.get("fat_g", 0),
            fiber_g=macros_data.get("fiber_g"),
        ),
        source="manual",
        confidence=analysis.get("confidence"),
    )

    # Log to Firestore (fire-and-forget)
    firestore_svc.log_meal_fire_and_forget(user_id, meal.model_dump())

    return ManualLogResponse(
        meal=meal,
        message=f"Logged: {meal.food_name}. Macros estimated successfully!",
    )


def _safe_meal_type(value: str) -> MealType:
    """Safely convert a string to MealType, defaulting to SNACK."""
    try:
        return MealType(value.lower())
    except (ValueError, AttributeError):
        return MealType.SNACK
