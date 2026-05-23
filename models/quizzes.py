from pydantic import BaseModel
from typing import Optional

class Quiz(BaseModel):
    title: str
    attempts: Optional[int] = None
    score: Optional[float] = None
    time_spent_ms: Optional[int] = None
