from fastapi import APIRouter, Depends
from minimemo.common.result import Result
from minimemo.repository.dependencies import get_session_repo

router = APIRouter()

@router.post("/MiniMemo/session/register")
async def register_session(agent_id: str, session_id: str, session_rep=Depends(get_session_repo)):
    """
    手动注册一个会话到指定智能体下
    会话id由调用方传入
    """
    session_rep.register_session(agent_id, session_id)
    return Result.success()
