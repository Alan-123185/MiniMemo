from fastapi import APIRouter, Depends

from common.exceptions import NotFoundException
from  common.requestSchema.searchRequest import searchRequest
from  common.requestSchema.storeRequest import originContentStoreRequest
from  common.result import Result
from  service.dependencies import get_memory_service
from repository.dependencies import get_agent_repo


"""
11.14
这个类暂时先不管
"""

router=APIRouter()

@router.post("/MiniMemo/memory/add")
async def add_memory(store_request:originContentStoreRequest, user_id: str,
                     memory_service=Depends(get_memory_service), agent_rep=Depends(get_agent_repo)):
    """
    外部调用 只能指定添加初始内容记忆
    """
    agent = await agent_rep.get_agent(agent_name=store_request.agent_name, user_id=user_id)
    if agent is None:
        raise NotFoundException("Agent 不存在")
    await memory_service.add_origin_content(
        store_request.model_copy(update={"agent_name": agent.id}), user_id=user_id
    )
    return Result.success()



@router.post("/MiniMemo/memory/search")
async def search_memory(search_request:searchRequest,
                        memory_service=Depends(get_memory_service), agent_rep=Depends(get_agent_repo)):
    """
    搜索指定智能体的记忆
    """
    agent = await agent_rep.get_agent(agent_name=search_request.agent_name, user_id=user_id)
    if agent is None:
        raise NotFoundException("Agent 不存在")
    memories=await memory_service.search_memory(
        search_request.model_copy(update={"agent_name": agent.id}), user_id=user_id
    )
    return Result(response=[{"id": memory.id, "content": memory.content} for memory in memories])

# @router.post("/MiniMemo/memory/searchOriginContent")
# async def search_origin_content(search_request:searchRequest,memory_service=Depends(get_memory_service)):
#     """
#     搜索指定智能体的原文
#     """
#     contents=await memory_service.search_origin_content(search_request)
#     return Result(response=[{"id": content.id, "content": content.content} for content in contents])




