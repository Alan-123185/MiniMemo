from pathlib import Path
from pydantic_settings import BaseSettings

ENV_FILE=Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}

    DEFAULT_BASE_URL:str=""

    DEFAULT_MODEL:str=""

    DEFAULT_API_KEY:str=""

    DEFAULT_EMBEDDING_MODEL:str=""

    DB_PATH:str="sqlite:///"+"D:/IDEA文件/python文件/MiniMemo/identifier.sqlite"


    MAX_RETRY_TIMES:int=3   #大模型请求失败最大重试次数


    SIMILARITY_THRESHOLD:float=0.85  #相似度阈值，超过该阈值的记忆将被认为是重复的

    TOP_K:int=3    #搜索记忆时的最大返回条数

    SIM_TO_THROW:float=0.95  #相似度超过该阈值的记忆将被丢弃，不再存储

    MAX_UNARCHIVED:int=10    #一个会话内未归档的原文最大数量，超过该数量将触发自动归档

    MAX_UNARCHIVED_TIME:int=60*30  #一个会话内未归档的原文最大时间，超过该时间将触发自动归档

    EPISODIC_CONSOLIDATION_INTERVAL:int=60*5  #情景记忆归档的时间间隔，单位秒


    negative_words:list[str]=["不", "没", "无", "别", "勿", "非", "未", "莫", "甭", "不要", "没有"]  #负面词汇列表，用于过滤记忆中的负面内容

settings = Settings()