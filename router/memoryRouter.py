from fastapi import APIRouter, Depends

from common.exceptions import NotFoundException
from  common.requestSchema.searchRequest import searchRequest
from  common.requestSchema.storeRequest import originContentStoreRequest
from  common.result import Result
from  service.dependencies import get_memory_service, get_search_service
from repository.dependencies import get_agent_repo


"""
11.14
这个类暂时先不管
"""

router=APIRouter()

@router.post("/MiniMemo/memory/search")
async def search_memory(search_request:searchRequest,
                        search_service=Depends(get_search_service), agent_rep=Depends(get_agent_repo)):
    """
    搜索指定智能体的记忆
    """
    agent = await agent_rep.get_agent(agent_name=search_request.agent_id, user_id=search_request.user_id)
    if agent is None:
        raise NotFoundException("Agent 不存在")
    search_request.agent_id=agent.id
    result=await search_service.search_memory(search_request)
    return Result(response=result)

