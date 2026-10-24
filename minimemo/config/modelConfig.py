from typing import Optional

from pydantic import BaseModel

from minimemo.config.data import settings


class modelConfig(BaseModel):
    model_name:str
    base_url:str
    api_key:str


class modelPool(BaseModel):
    embedding:modelConfig=modelConfig(model_name=settings.DEFAULT_EMBEDDING_MODEL,base_url=settings.DEFAULT_BASE_URL,api_key=settings.DEFAULT_API_KEY)
    chat:modelConfig=modelConfig(model_name=settings.DEFAULT_MODEL,base_url=settings.DEFAULT_BASE_URL,api_key=settings.DEFAULT_API_KEY)

_model_pool: Optional[modelPool] = None

def get_pool() -> modelPool:
    if _model_pool is None:
        raise RuntimeError("模型池未初始化")
    return _model_pool

def set_pool(pool: modelPool=modelPool()):
    global _model_pool
    _model_pool = pool

