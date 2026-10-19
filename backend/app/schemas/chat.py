from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class ConciergeReply(BaseModel):
    text: str
    intent: str = "answer"  # answer, modify, regenerate, clarify
    instruction: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    version_change: bool = False
    diff: Optional[Dict[str, Any]] = None
    trace: List[str] = Field(default_factory=list)


class ChatMessageResponse(BaseModel):
    id: Union[int, str]
    trip_id: Union[int, str]
    role: str
    content: str
    intent: Optional[str] = None
    version_before: Optional[int] = None
    version_after: Optional[int] = None
    created_at: str
