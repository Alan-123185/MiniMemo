from typing import Literal, Optional

from pydantic import BaseModel


class memoryInfo(BaseModel):
    """
    记忆信息
    """
    embedding: bytes
    embedding_model: str
    content:str
    origin_content_id: Optional[str] = None


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