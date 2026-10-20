from fastapi import APIRouter, Depends

from common.result import Result
from repository.dependencies import get_agent_repo

router = APIRouter()

@router.get("/MiniMemo/agents")
async def get_agents():
    """
    获取所有被记忆接管的智能体列表
    """
    return Result.success()

@router.post("/MiniMemo/register_agent")
async def register_agent(agent_id: str,agent_rep=Depends(get_agent_repo)):
    """
    注册一个智能体到记忆接管系统
    带唯一标识符
    """
    agent_rep.register_agent(agent_id)
    return Result.success()

