from fastapi import APIRouter

from common.result import Result
from config.modelConfig import modelPool
from config import modelConfig

router=APIRouter()

@router.get("/MiniMemo/model/list")
async def get_models():
    """
    获取所有可用的模型列表
    """
    return Result(response=modelConfig.get_pool())

@router.post("/MiniMemo/model/set")
async def set_model(payload: modelPool):
    """
    设置当前使用的模型
    """
    modelConfig.set_pool(payload)
    return Result.success()