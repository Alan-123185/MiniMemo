from fastapi import APIRouter, Depends

from  minimemo.common.requestSchema.searchRequest import searchRequest
from  minimemo.common.requestSchema.storeRequest import storeRequest, episodeStoreRequest, semanticStoreRequest
from  minimemo.common.result import Result
from  minimemo.service.dependencies import get_memory_service

router=APIRouter()

@router.post("/MiniMemo/memory/addSemantic")
async def add_semantic_memory(store_request:semanticStoreRequest,memory_service=Depends(get_memory_service)):
    """
    为指定的智能体添加语义记忆
    原文会先落 origin_content，再由大模型提炼成事实/偏好
    """
    await memory_service.add_semantic_memory(store_request)
    return Result.success()

@router.post("/MiniMemo/memory/addEpisodic")
async def add_episodic_memory(store_request:episodeStoreRequest,memory_service=Depends(get_memory_service)):
    """
    为指定的智能体添加情景记忆，原文原样入库
    """
    await memory_service.add_episodic_memory(store_request)
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

