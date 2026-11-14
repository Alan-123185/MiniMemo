from pydantic import BaseModel


class searchRequest(BaseModel):
    agent_id: str
    query: str #单个关键语句
    user_id: str

class searchEpisodesRequest(searchRequest):
    agent_id: str
    query: str

class searchSemanticsRequest(searchRequest):
    agent_id: str
    query: str






