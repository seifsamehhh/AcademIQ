from pydantic import BaseModel
from typing import Optional

class Course(BaseModel):
    course_id: str
    name: str
    visits: int
    time_spent_ms: int
    final_grade: Optional[str] = None
