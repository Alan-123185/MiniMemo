from fastapi import APIRouter, Depends
from common.exceptions import NotFoundException
from common.requestSchema.storeRequest import originContentStoreRequest
from common.result import Result
from service.consolidationService import consolidationService
from repository.dependencies import get_agent_repo
from service.dependencies import get_memory_service


router = APIRouter()


@router.post("/MiniMemo/consolidation/add_episodic_memory/{agent_name}/session/{session_id}")
async def episodic_memory_consolidation(agent_name: str,session_id: str, user_id: str,
                                       agent_rep=Depends(get_agent_repo)):
    """
    调用接口主动触发情景记忆抽取
    """
    internal_agent_id = await agent_rep.get_agent(user_id, agent_name).id
    await consolidationService.consolidate_episodics(internal_agent_id, session_id)
    return Result.success()

@router.post("/MiniMemo/consolidation/add_semantinc_memory/{agent_name}")
async def semantic_memory_consolidation(agent_name: str, user_id: str, agent_rep=Depends(get_agent_repo)):
    """
    调用接口主动触发语义记忆抽取
    """
    internal_agent_id = await agent_rep.get_agent(user_id, agent_name).id
    await consolidationService.consolidate_semantics(internal_agent_id)
    return Result.success()



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