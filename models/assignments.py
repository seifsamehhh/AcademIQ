from pydantic import BaseModel
from typing import Optional

class Assignment(BaseModel):
    title: str
    due_date: str
    submitted: bool = False
    grade: Optional[str] = None
