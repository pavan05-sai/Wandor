from collections import defaultdict
from typing import Any
from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user, get_owned_trip
from app.core.errors import NotFoundError
from app.models.database import get_db
from app.repositories.base import EntityDoc
from app.repositories.entities import ExpenseRepository
from app.repositories.trips import TripRepository
from app.repositories.versions import VersionRepository
from app.schemas.common import success_response
from app.schemas.itinerary import CanonicalItinerary

router = APIRouter(tags=["Analytics"])


@router.get("/trips/{trip_id}/analytics")
def get_trip_analytics(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    exp_repo = ExpenseRepository(db)

    v = version_repo.get_latest(trip.id)
    if not v or not v.json:
        raise NotFoundError("No itinerary found for analytics")

    it = CanonicalItinerary(**v.json)
    expenses = exp_repo.list_by_trip(trip.id)

    # Actual spending
    actual_by_category = defaultdict(int)
    actual_by_day = defaultdict(int)
    total_actual = 0
    for e in expenses:
        actual_by_category[e.category] += e.amount
        if e.day_id:
            actual_by_day[e.day_id] += e.amount
        total_actual += e.amount

    # Planned spending
    planned_breakdown = it.budget.breakdown.model_dump()
    planned_total = it.budget.estimated_total

    # Day loads & time split
    time_split_by_day = []
    total_active_mins = 0
    total_travel_mins = 0

    for d in it.days:
        time_split_by_day.append({
            "day_number": d.day_number,
            "day_id": d.id,
            "active_minutes": d.totals.active_minutes,
            "travel_minutes": d.totals.travel_minutes,
            "planned_cost": d.totals.activity_cost + d.totals.food_cost + d.totals.transport_cost,
            "actual_cost": actual_by_day.get(d.id, 0)
        })
        total_active_mins += d.totals.active_minutes
        total_travel_mins += d.totals.travel_minutes

    return success_response({
        "planned_vs_actual": {
            "planned_total": planned_total,
            "actual_total": total_actual,
            "variance": total_actual - planned_total
        },
        "planned_by_category": planned_breakdown,
        "actual_by_category": dict(actual_by_category),
        "time_distribution": {
            "total_active_minutes": total_active_mins,
            "total_travel_minutes": total_travel_mins,
            "by_day": time_split_by_day
        }
    })


@router.get("/analytics/overview")
def get_user_analytics_overview(
    user: EntityDoc = Depends(get_current_user),
    db: Any = Depends(get_db)
):
    trip_repo = TripRepository(db)
    exp_repo = ExpenseRepository(db)

    trips = trip_repo.list_by_user(user.id)
    total_trips = len(trips)
    total_days = sum(t.num_days for t in trips)

    total_spent = 0
    for t in trips:
        exps = exp_repo.list_by_trip(t.id)
        total_spent += sum(e.amount for e in exps)

    return success_response({
        "total_trips": total_trips,
        "total_days_traveled": total_days,
        "total_expenses_logged": total_spent
    })
