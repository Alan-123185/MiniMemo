from pydantic import BaseModel


class searchRequest(BaseModel):
    agent_name: str
    query: list[str]