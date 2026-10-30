from fastapi import APIRouter, Depends

from  minimemo.common.requestSchema.searchRequest import searchRequest
from  minimemo.common.requestSchema.storeRequest import originContentStoreRequest
from  minimemo.common.result import Result
from  minimemo.service.dependencies import get_memory_service

router=APIRouter()

@router.post("/MiniMemo/memory/add")
async def add_semantic_memory(store_request:originContentStoreRequest,memory_service=Depends(get_memory_service)):
    """
    外部调用 只能指定添加初始内容记忆
    """
    await memory_service.add_origin_content(store_request)
    return Result.success()

@router.post("/MiniMemo/memory/search")
async def search_memory(search_request:searchRequest,memory_service=Depends(get_memory_service)):
    """
    搜索指定智能体的记忆
    """
    memories=await memory_service.search_memory(search_request)
    return Result(response=[{"id": memory.id, "content": memory.content} for memory in memories])

@router.post("/MiniMemo/memory/searchOriginContent")
async def search_origin_content(search_request:searchRequest,memory_service=Depends(get_memory_service)):
    """
    搜索指定智能体的原文
    """
    contents=await memory_service.search_origin_content(search_request)
    return Result(response=[{"id": content.id, "content": content.content} for content in contents])

