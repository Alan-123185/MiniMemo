from fastapi import APIRouter, Depends
from common.result import Result
from repository.dependencies import get_agent_repo

router = APIRouter()

@router.get("/MiniMemo/agent/list/{user_id}")
async def get_agents(user_id: str, agent_rep=Depends(get_agent_repo)):
    """
    获取指定用户下被记忆接管的智能体列表
    """
    agent_list = await agent_rep.get_agents(user_id)
    return Result(response=[agent.agent_name for agent in agent_list])

@router.post("/MiniMemo/agent/register/{user_id}/{agent_name}")
async def register_agent(agent_name: str, user_id: str, agent_rep=Depends(get_agent_repo)):
    """
    注册一个智能体到记忆接管系统
    带唯一标识符
    """
    await agent_rep.register_agent(agent_name, user_id)
    return Result.success()
