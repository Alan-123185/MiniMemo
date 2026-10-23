from fastapi import APIRouter, Depends

from common.result import Result
from models import Agent
from repository.dependencies import get_agent_repo

router = APIRouter()

@router.get("/MiniMemo/agent/list")
async def get_agents(agent_rep=Depends(get_agent_repo)):
    """
    获取所有被记忆接管的智能体列表
    """
    agent_list = agent_rep.get_agents()
    return Result(response=agent_list)

@router.post("/MiniMemo/agent/register")
async def register_agent(agent_id: str,agent_rep=Depends(get_agent_repo)):
    """
    注册一个智能体到记忆接管系统
    带唯一标识符
    """
    await agent_rep.register_agent(Agent(agent_id))
    return Result.success()


