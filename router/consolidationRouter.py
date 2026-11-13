from fastapi import APIRouter, Depends

from common.result import Result
from service.consolidationService import consolidationService

router = APIRouter()




@router.post("/MiniMemo/consolidation/add_episodic_memory/{agent_id}/session/{session_id}")
async def episodic_memory_consolidation(agent_id: str,session_id: str):
    """
    调用接口主动触发情景记忆抽取
    """
    await consolidationService.consolidate_episodics(agent_id, session_id)
    return Result.success()

@router.post("/MiniMemo/consolidation/add_semantinc_memory/{agent_id}")
async def semantic_memory_consolidation(agent_id: str):
    """
    调用接口主动触发语义记忆抽取
    """
    await consolidationService.consolidate_semantics(agent_id)
    return Result.success()