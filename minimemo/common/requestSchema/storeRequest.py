from typing import Optional, Literal

from pydantic import BaseModel


class storeRequest(BaseModel):
    agent_id:str
    origin_content:str

class episodeStoreRequest(storeRequest):
    """
    用于存储情景记忆的请求对象
    """
    role: Literal["user", "assistant", "system"]  # 消息类型 用户还是智能体，系统

class semanticStoreRequest(storeRequest):
    """
    用于存储语义记忆的请求对象
    """
    additional_kwargs : Optional[dict] = None  # 可选的附加参数，用于帮助llm整合记忆
    