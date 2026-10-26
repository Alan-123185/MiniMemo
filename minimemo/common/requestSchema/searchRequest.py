from pydantic import BaseModel


class searchRequest(BaseModel):
    agent_id: str
    query: list[str]