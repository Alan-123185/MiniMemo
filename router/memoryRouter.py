from fastapi import APIRouter, Depends

from common.requestSchema.storeRequest import storeRequest
from common.result import Result
from service.dependencies import get_memory_service

router=APIRouter()

@router.post("/MiniMemo/memory/add")
async def add_memory(store_request:storeRequest,store_service=Depends(get_memory_service)):
    """
    为指定的智能体添加记忆
    """
    store_service.add_memory(store_request)
    return Result()
