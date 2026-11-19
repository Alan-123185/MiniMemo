from pydantic import BaseModel

from config.data import settings


class searchRequest(BaseModel):
    query: str #单个关键语句
    user_id: str
    agent_id:str  #注意 这个地方传进来应该是agent_name 但是在service里会被替换成agent_id
    return_count:int=settings.DEFAULT_RETURN_K  #最终返回的记忆数量






#
# class searchEpisodesRequest(searchRequest):
#     agent_id: str
#     query: str
#
# class searchSemanticsRequest(searchRequest):
#     agent_id: str
#     query: str






