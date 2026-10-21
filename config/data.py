from pathlib import Path

from pydantic.v1 import BaseSettings


ENV_FILE=Path(__file__).resolve().parent / ".env"

class Settings(BaseSettings):
    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}

    DEFAULT_BASE_URL:str=""

    DEFAULT_MODEL:str=""

    DEFAULT_API_KEY:str=""

    DB_PATH:str="sqlite:///./identifier.sqlite"


    MAX_RETRY_TIMES:int=3   #大模型请求失败最大重试次数


    SIMILARITY_THRESHOLD:float=0.85  #相似度阈值，超过该阈值的记忆将被认为是重复的


settings = Settings()