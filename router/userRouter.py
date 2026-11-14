from fastapi import APIRouter, Depends
from common.result import Result
from config.modelConfig import UserModelConfig
from repository.dependencies import get_user_repo
from repository.userRepository import userRepository

router = APIRouter()


@router.post("/MiniMemo/user/register")
async def register_user(
    user_id: str,
    payload: UserModelConfig | None = None,
    user_rep: userRepository = Depends(get_user_repo),
):
    """创建用户，可在同一事务里写入初始模型配置。"""
    await user_rep.register_user(user_id, payload)
    return Result.success()




