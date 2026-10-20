from fastapi import APIRouter, Depends

from common.result import Result
from service.dependencies import get_memory_service

router=APIRouter()

@router.post("/MiniMemo/memory/add")
async def add_memory(agent_id: str, origin_content:str,memory_service=Depends(get_memory_service)):
    """
    为指定的智能体添加记忆
    """
    memory_service.add_memory(agent_id,origin_content)
    return Result()
