from pydantic import BaseModel

class Session(BaseModel):
    start: int
    end: int
    duration_ms: int
