from pydantic import BaseModel


class bm25Result(BaseModel):
    memory_id: str
    memory_type: str
    score: float
