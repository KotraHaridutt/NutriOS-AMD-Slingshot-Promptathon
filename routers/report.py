"""
NutriOS — Weekly Report Router

GET /report/weekly — Generates a behavioral habit report with scoring.
Returns JSON or rendered HTML based on Accept header / format query param.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from middleware.auth import get_current_user_id
from models.schemas import (
    DailyBreakdown,
    ErrorResponse,
    HabitScore,
    WeeklyReport,
)
from services import firestore_svc, gemini

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["Reports"])


@router.get(
    "/weekly",
    response_model=WeeklyReport,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Get weekly habit report",
    description=(
        "Generates a comprehensive weekly nutrition and habit report. "
        "Includes daily breakdown, habit scoring (consistency, variety, timing), "
        "streak tracking, and AI-generated insights. "
        "Add `?format=html` for a rendered HTML report."
    ),
)
async def get_weekly_report(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    format: str = Query(
        default="json",
        description="Response format: 'json' or 'html'",
    ),
):
    """
    Generate the weekly habit report.

    Scoring philosophy: We reward consistency, variety, and timing —
    not just calorie counting. A user who eats 3 varied meals at
    regular times scores higher than one who hits exact calorie targets
    but skips meals randomly.
    """
    logger.info("Weekly report requested by user %s (format=%s)", user_id, format)

    # Calculate date range (last 7 days)
    now = datetime.now(timezone.utc)
    end_date = now.isoformat()
    start_date = (now - timedelta(days=7)).isoformat()

    # Fetch meals and profile
    meals = await firestore_svc.get_meals_for_period(user_id, start_date, end_date)
    profile = await firestore_svc.get_user_profile(user_id)

    # Build daily breakdown
    daily_breakdown = _build_daily_breakdown(meals, now)

    # Calculate habit scores
    habit_score = _calculate_habit_score(meals, daily_breakdown)

    # Generate AI insights
    weekly_summary = _build_weekly_summary(daily_breakdown, meals)
    user_context = {
        "name": profile.get("name", "User") if profile else "User",
        "goals": profile.get("goal", "eat_healthier") if profile else "eat_healthier",
    }
    habit_scores_dict = {
        "overall": habit_score.overall_score,
        "consistency": habit_score.consistency_score,
        "variety": habit_score.variety_score,
        "timing": habit_score.timing_score,
    }
    insights = await gemini.generate_weekly_insights(
        user_context, weekly_summary, habit_scores_dict
    )

    # Average daily calories
    total_cals = sum(d.total_calories for d in daily_breakdown)
    days_with_data = sum(1 for d in daily_breakdown if d.meal_count > 0)
    avg_daily_cals = total_cals / days_with_data if days_with_data > 0 else 0

    report = WeeklyReport(
        user_id=user_id,
        period_start=start_date[:10],
        period_end=end_date[:10],
        daily_breakdown=daily_breakdown,
        average_daily_calories=round(avg_daily_cals, 1),
        habit_score=habit_score,
        insights=insights,
        message="Your weekly report is ready!",
    )

    if format.lower() == "html":
        return _render_html_report(report)

    return report


def _build_daily_breakdown(
    meals: List[Dict[str, Any]],
    now: datetime,
) -> List[DailyBreakdown]:
    """Build a per-day calorie/macro breakdown for the past 7 days."""
    # Initialize all 7 days
    daily: Dict[str, Dict[str, float]] = {}
    for i in range(7):
        date = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        daily[date] = {
            "calories": 0.0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "meal_count": 0,
        }

    for meal in meals:
        logged_at = meal.get("logged_at", "")[:10]
        if logged_at in daily:
            macros = meal.get("macros", {})
            if isinstance(macros, dict):
                daily[logged_at]["calories"] += macros.get("calories", 0)
                daily[logged_at]["protein_g"] += macros.get("protein_g", 0)
                daily[logged_at]["carbs_g"] += macros.get("carbs_g", 0)
                daily[logged_at]["fat_g"] += macros.get("fat_g", 0)
            daily[logged_at]["meal_count"] += 1

    return [
        DailyBreakdown(
            date=date,
            total_calories=round(data["calories"], 1),
            total_protein_g=round(data["protein_g"], 1),
            total_carbs_g=round(data["carbs_g"], 1),
            total_fat_g=round(data["fat_g"], 1),
            meal_count=int(data["meal_count"]),
        )
        for date, data in sorted(daily.items())
    ]


def _calculate_habit_score(
    meals: List[Dict[str, Any]],
    daily_breakdown: List[DailyBreakdown],
) -> HabitScore:
    """
    Calculate behavioral habit scores.

    Scoring axes:
    - Consistency (40%): Did the user log meals regularly?
    - Variety (30%): How diverse were the foods eaten?
    - Timing (30%): Were meals at regular, healthy times?

    Philosophy: We reward BEHAVIOR, not just numbers.
    """
    # ── Consistency Score ────────────────────────────────────
    days_with_meals = sum(1 for d in daily_breakdown if d.meal_count > 0)
    consistency = (days_with_meals / 7) * 100

    # Bonus for 3+ meals per day
    well_fed_days = sum(1 for d in daily_breakdown if d.meal_count >= 3)
    consistency_bonus = (well_fed_days / 7) * 20
    consistency = min(consistency + consistency_bonus, 100)

    # ── Variety Score ────────────────────────────────────────
    unique_foods: Set[str] = set()
    meal_types_seen: Set[str] = set()
    for meal in meals:
        food_name = meal.get("food_name", "").lower().strip()
        if food_name:
            unique_foods.add(food_name)
        meal_type = meal.get("meal_type", "")
        if meal_type:
            meal_types_seen.add(meal_type)

    # More unique foods = higher variety
    variety = min((len(unique_foods) / 14) * 100, 100)  # 14 unique in 7 days = perfect

    # Bonus for hitting all meal types
    type_bonus = (len(meal_types_seen) / 4) * 15
    variety = min(variety + type_bonus, 100)

    # ── Timing Score ─────────────────────────────────────────
    # Check if meals are at consistent times
    meal_hours: Dict[str, List[int]] = defaultdict(list)
    for meal in meals:
        logged_at = meal.get("logged_at", "")
        meal_type = meal.get("meal_type", "")
        if logged_at and meal_type:
            try:
                dt = datetime.fromisoformat(logged_at)
                meal_hours[meal_type].append(dt.hour)
            except (ValueError, TypeError):
                pass

    timing = 70.0  # Base score
    for meal_type, hours in meal_hours.items():
        if len(hours) >= 2:
            avg_hour = sum(hours) / len(hours)
            variance = sum((h - avg_hour) ** 2 for h in hours) / len(hours)
            # Low variance = consistent timing = bonus
            if variance < 2:
                timing += 10
            elif variance < 4:
                timing += 5
    timing = min(timing, 100)

    # ── Streak Calculation ───────────────────────────────────
    streak = 0
    for day in reversed(daily_breakdown):
        if day.meal_count > 0:
            streak += 1
        else:
            break

    # ── Overall Score (weighted) ─────────────────────────────
    overall = (
        consistency * 0.40
        + variety * 0.30
        + timing * 0.30
    )

    return HabitScore(
        overall_score=round(overall, 1),
        consistency_score=round(consistency, 1),
        variety_score=round(variety, 1),
        timing_score=round(timing, 1),
        streak_days=streak,
    )


def _build_weekly_summary(
    daily_breakdown: List[DailyBreakdown],
    meals: List[Dict[str, Any]],
) -> str:
    """Build a text summary of the week for AI insight generation."""
    total_meals = sum(d.meal_count for d in daily_breakdown)
    total_cals = sum(d.total_calories for d in daily_breakdown)
    days_logged = sum(1 for d in daily_breakdown if d.meal_count > 0)

    food_names = [m.get("food_name", "") for m in meals if m.get("food_name")]
    unique_count = len(set(food_names))

    lines = [
        f"Total meals logged: {total_meals} across {days_logged}/7 days",
        f"Total calories: {total_cals:.0f} (avg {total_cals/7:.0f}/day)",
        f"Unique foods: {unique_count}",
    ]

    for day in daily_breakdown:
        lines.append(
            f"  {day.date}: {day.meal_count} meals, "
            f"{day.total_calories:.0f} cal, "
            f"P:{day.total_protein_g:.0f}g C:{day.total_carbs_g:.0f}g F:{day.total_fat_g:.0f}g"
        )

    return "\n".join(lines)


def _render_html_report(report: WeeklyReport) -> HTMLResponse:
    """Render the weekly report as semantic, accessible HTML."""
    # Build daily rows
    daily_rows = ""
    for day in report.daily_breakdown:
        bar_width = min(day.total_calories / 25, 100)  # Scale for visual bar
        daily_rows += f"""
        <tr>
            <td>{day.date}</td>
            <td>{day.meal_count}</td>
            <td>
                <div class="cal-bar" style="width: {bar_width}%" aria-label="{day.total_calories:.0f} calories">
                    {day.total_calories:.0f}
                </div>
            </td>
            <td>{day.total_protein_g:.0f}g</td>
            <td>{day.total_carbs_g:.0f}g</td>
            <td>{day.total_fat_g:.0f}g</td>
        </tr>"""

    # Build insights list
    insights_html = "".join(
        f'<li>{insight}</li>' for insight in report.insights
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NutriOS Weekly Report — {report.period_start} to {report.period_end}</title>
    <style>
        :root {{
            --primary: #10b981;
            --primary-dark: #059669;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --accent: #6366f1;
            --warning: #f59e0b;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            padding: 2rem;
            line-height: 1.6;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        header {{
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: linear-gradient(135deg, var(--primary-dark), var(--accent));
            border-radius: 16px;
        }}
        header h1 {{
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}
        header p {{ color: var(--text-muted); margin-top: 0.5rem; }}
        .score-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        .score-card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
        }}
        .score-value {{
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--primary);
        }}
        .score-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.25rem;
        }}
        .section {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1.5rem 0;
        }}
        .section h2 {{
            font-size: 1.25rem;
            margin-bottom: 1rem;
            color: var(--primary);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        th {{ color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; }}
        .cal-bar {{
            background: linear-gradient(90deg, var(--primary), var(--accent));
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            min-width: 40px;
            text-align: center;
        }}
        .insights ul {{
            list-style: none;
            padding: 0;
        }}
        .insights li {{
            padding: 0.75rem 1rem;
            background: rgba(99, 102, 241, 0.1);
            border-left: 3px solid var(--accent);
            margin-bottom: 0.5rem;
            border-radius: 0 8px 8px 0;
        }}
        .streak-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            padding: 0.5rem 1rem;
            border-radius: 100px;
            font-weight: 700;
            font-size: 1.1rem;
        }}
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-top: 2rem;
        }}
    </style>
</head>
<body>
    <main class="container" role="main">
        <header role="banner">
            <h1 aria-label="NutriOS Weekly Report">🍎 NutriOS Weekly Report</h1>
            <p>{report.period_start} — {report.period_end}</p>
            <div class="streak-badge" aria-label="{report.habit_score.streak_days} day streak">
                🔥 {report.habit_score.streak_days}-day streak
            </div>
        </header>

        <section class="score-grid" aria-label="Habit Scores">
            <div class="score-card">
                <div class="score-value" aria-label="Overall score">{report.habit_score.overall_score:.0f}</div>
                <div class="score-label">Overall Score</div>
            </div>
            <div class="score-card">
                <div class="score-value">{report.habit_score.consistency_score:.0f}</div>
                <div class="score-label">Consistency</div>
            </div>
            <div class="score-card">
                <div class="score-value">{report.habit_score.variety_score:.0f}</div>
                <div class="score-label">Variety</div>
            </div>
            <div class="score-card">
                <div class="score-value">{report.habit_score.timing_score:.0f}</div>
                <div class="score-label">Timing</div>
            </div>
        </section>

        <section class="section" aria-label="Average Daily Calories">
            <h2>📊 Average Daily Calories</h2>
            <p style="font-size: 1.8rem; font-weight: 800; color: var(--primary);">
                {report.average_daily_calories:.0f} kcal/day
            </p>
        </section>

        <section class="section" aria-label="Daily Breakdown">
            <h2>📅 Daily Breakdown</h2>
            <table role="table">
                <thead>
                    <tr>
                        <th scope="col">Date</th>
                        <th scope="col">Meals</th>
                        <th scope="col">Calories</th>
                        <th scope="col">Protein</th>
                        <th scope="col">Carbs</th>
                        <th scope="col">Fat</th>
                    </tr>
                </thead>
                <tbody>
                    {daily_rows}
                </tbody>
            </table>
        </section>

        <section class="section insights" aria-label="AI Insights">
            <h2>💡 AI Insights</h2>
            <ul>
                {insights_html}
            </ul>
        </section>

        <footer role="contentinfo">
            <p>Generated by NutriOS · Powered by Gemini AI · {report.generated_at}</p>
        </footer>
    </main>
</body>
</html>"""

    return HTMLResponse(content=html, status_code=200)
