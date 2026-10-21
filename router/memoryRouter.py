from fastapi import APIRouter, Depends

from common.requestSchema.storeRequest import memoryRequest
from common.result import Result
from service.dependencies import get_memory_service

router=APIRouter()

@router.post("/MiniMemo/memory/add")
async def add_memory(memory_request:memoryRequest,store_service=Depends(get_memory_service)):
    """
    为指定的智能体添加记忆
    """
    store_service.add_memory(memory_request)
    return Result()
