from typing import Optional

from pydantic import BaseModel


class storeRequest(BaseModel):
    agent_id:str
    origin_content:str
    additional_kwargs:Optional[dict] = None   #自由参数