from typing import Literal
from fastapi import APIRouter, Depends
from common.result import Result
from config.modelConfig import UserModelConfig
from repository.dependencies import get_user_repo
from repository.userRepository import userRepository


router = APIRouter()

@router.get("/MiniMemo/model/list")
async def get_models(user_id: str, user_rep: userRepository = Depends(get_user_repo)):
    """查询指定用户的模型配置，响应中省略 API Key。"""
    config = await user_rep.get_models(user_id)
    #排除api_key字段
    return Result(response=config.model_dump(
        mode="json", exclude={"embedding": {"api_key"}, "chat": {"api_key"}}
    ))


@router.post("/MiniMemo/model/add")
async def add_model(
    user_id: str, payload: UserModelConfig, user_rep: userRepository = Depends(get_user_repo)
):
    """给用户添加未配置的模型。"""
    await user_rep.add_models(user_id, payload)
    return Result.success()


@router.post("/MiniMemo/model/set")
async def set_model(
    user_id: str, payload: UserModelConfig, user_rep: userRepository = Depends(get_user_repo)
):
    """更新请求中指定的已有模型。"""
    await user_rep.update_models(user_id, payload)
    return Result.success()


@router.delete("/MiniMemo/model/delete")
async def delete_model(
    user_id: str,
    kind: Literal["embedding", "chat"],
    user_rep: userRepository = Depends(get_user_repo),
):
    """清空指定用户的一项模型配置。"""
    await user_rep.delete_model(user_id, kind)
    return Result.success()