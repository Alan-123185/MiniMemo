from fastapi import APIRouter, Depends

from  minimemo.common.requestSchema.searchRequest import searchRequest
from  minimemo.common.requestSchema.storeRequest import storeRequest
from  minimemo.common.result import Result
from  minimemo.service.dependencies import get_memory_service

router=APIRouter()

@router.post("/MiniMemo/memory/add")
async def add_memory(store_request:storeRequest,memory_service=Depends(get_memory_service)):
    """
    为指定的智能体添加记忆
    """
    await memory_service.add_memory(store_request)
    return Result.success()

@router.post("/MiniMemo/memory/search")
async def search_memory(search_request:searchRequest,memory_service=Depends(get_memory_service)):
    """
    搜索指定智能体的记忆
    """
    memories=await memory_service.search_memory(search_request)
    return Result(response=[{"id": memory.id, "content": memory.content} for memory in memories])

