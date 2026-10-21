from typing import Optional

from pydantic import BaseModel


class modelConfig(BaseModel):
    model_name:str
    base_url:str
    api_key:str


class modelPool(BaseModel):
    embedding:modelConfig
    chat:modelConfig

_model_pool: Optional[modelPool] = None

def get_pool() -> modelPool:
    if _model_pool is None:
        raise RuntimeError("模型池未初始化")
    return _model_pool

def set_pool(pool: modelPool):
    global _model_pool
    _model_pool = pool
