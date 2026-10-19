from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    category: str = Field(description="accommodation, transport, food, activities, misc")
    amount: int = Field(gt=0, description="Amount spent in INR")
    day_id: Optional[str] = None
    note: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: Union[int, str]
    trip_id: Union[int, str]
    day_id: Optional[str] = None
    category: str
    amount: int
    note: Optional[str] = None
    spent_at: str


class ExpenseTotalsResponse(BaseModel):
    expenses: List[ExpenseResponse]
    totals_by_category: Dict[str, int]
    total_spent: int
    planned_total: int
    remaining_budget: int
