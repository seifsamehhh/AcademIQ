from pydantic import BaseModel
from typing import Optional, List, Dict

class RawMoodlePayload(BaseModel):
    student_id: Optional[str] = None
    clicks: int
    lastActivity: int
    sessions: List[Dict] = []
    courses: Dict = {}
