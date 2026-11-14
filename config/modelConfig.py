from pydantic import BaseModel, ConfigDict
from config.data import settings


class modelConfig(BaseModel):
    model_name:str
    base_url:str
    api_key:str


class UserModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding: modelConfig | None = None
    chat: modelConfig | None = None


class modelPool(BaseModel):
    embedding:modelConfig=modelConfig(model_name=settings.DEFAULT_EMBEDDING_MODEL,base_url=settings.DEFAULT_BASE_URL,api_key=settings.DEFAULT_API_KEY)
    chat:modelConfig=modelConfig(model_name=settings.DEFAULT_MODEL,base_url=settings.DEFAULT_BASE_URL,api_key=settings.DEFAULT_API_KEY)
