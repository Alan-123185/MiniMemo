from fastapi import APIRouter, Depends
from common.result import Result
from repository.dependencies import get_agent_repo, get_session_repo

router = APIRouter()

@router.post("/MiniMemo/session/register")
async def register_session(agent_name: str, session_id: str, user_id: str,
                           session_rep=Depends(get_session_repo), agent_rep=Depends(get_agent_repo)):
    """
    手动注册一个会话到指定智能体下
    会话id由调用方传入
    """
    internal_agent_id = await agent_rep.get_agent(user_id, agent_name)
    await session_rep.register_session(internal_agent_id.id, session_id)
    return Result.success()
