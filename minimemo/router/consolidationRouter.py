from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/MiniMemo/consolidation/add_semantinc_memory/{agent_id}")
async def semantic_memory_consolidation(agent_id: str):
    """
    调用接口主动触发情景记忆抽取
    """


    
