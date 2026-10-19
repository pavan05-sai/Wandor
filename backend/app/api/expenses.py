from collections import defaultdict
from typing import Any
from fastapi import APIRouter, Depends, status
from app.api.dependencies import get_owned_trip
from app.core.errors import NotFoundError
from app.models.database import get_db
from app.repositories.base import EntityDoc
from app.repositories.entities import ExpenseRepository
from app.repositories.versions import VersionRepository
from app.schemas.common import success_response
from app.schemas.expenses import ExpenseCreate, ExpenseResponse, ExpenseTotalsResponse
from app.schemas.itinerary import CanonicalItinerary

router = APIRouter(prefix="/trips/{trip_id}", tags=["Expenses"])


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt or "")


@router.get("/budget")
def get_trip_budget(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    version_repo = VersionRepository(db)
    v = version_repo.get_latest(trip.id)
    if not v or not v.json:
        raise NotFoundError("No itinerary found")

    it = CanonicalItinerary(**v.json)
    return success_response(it.budget.model_dump())


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def log_expense(
    exp_in: ExpenseCreate,
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    repo = ExpenseRepository(db)
    expense = repo.create(
        trip_id=trip.id,
        category=exp_in.category,
        amount=exp_in.amount,
        day_id=exp_in.day_id,
        note=exp_in.note
    )
    return success_response(
        ExpenseResponse(
            id=expense.id,
            trip_id=expense.trip_id,
            day_id=expense.day_id,
            category=expense.category,
            amount=expense.amount,
            note=expense.note,
            spent_at=_iso(expense.spent_at)
        ).model_dump()
    )


@router.get("/expenses")
def list_expenses(
    trip: EntityDoc = Depends(get_owned_trip),
    db: Any = Depends(get_db)
):
    repo = ExpenseRepository(db)
    expenses = repo.list_by_trip(trip.id)

    version_repo = VersionRepository(db)
    latest_v = version_repo.get_latest(trip.id)
    planned_total = 0
    if latest_v and latest_v.json:
        planned_total = latest_v.json.get("budget", {}).get("estimated_total", 0)

    totals_by_cat = defaultdict(int)
    total_spent = 0
    exp_responses = []

    for e in expenses:
        totals_by_cat[e.category] += e.amount
        total_spent += e.amount
        exp_responses.append(ExpenseResponse(
            id=e.id,
            trip_id=e.trip_id,
            day_id=e.day_id,
            category=e.category,
            amount=e.amount,
            note=e.note,
            spent_at=_iso(e.spent_at)
        ))

    remaining = max(0, planned_total - total_spent)

    return success_response(
        ExpenseTotalsResponse(
            expenses=exp_responses,
            totals_by_category=dict(totals_by_cat),
            total_spent=total_spent,
            planned_total=planned_total,
            remaining_budget=remaining
        ).model_dump()
    )
