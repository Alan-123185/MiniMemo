import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class memoryInfo(BaseModel):
    """
    记忆信息
    """
    embedding: list[float]
    embedding_model: str
    content:str




class episodicMemoryInfo(memoryInfo):
    origin_content_id: Optional[list[str]] = None



class originContentMemoryInfo(memoryInfo):
    """
    情景记忆信息
    """
    role: str
    session_id: str



class semanticMemoryInfo(memoryInfo):
    """
    语义记忆信息
    """
    type: Literal["fact", "opinion", "hypothesis"] = "fact"
    is_alive: Optional[bool] = True




class returnMemoryInfo(BaseModel):
    """
    最终召回返回的记忆信息
    """
    content: str
    memory_type: Literal["origin", "episodic", "semantic"]
    update_time:datetime.datetime