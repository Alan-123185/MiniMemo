from pathlib import Path
from pydantic_settings import BaseSettings

ENV_FILE=Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}

    DEFAULT_BASE_URL:str=""

    DEFAULT_MODEL:str=""

    DEFAULT_API_KEY:str=""

    DEFAULT_EMBEDDING_MODEL:str=""

    DB_DSN:str=""   # PostgreSQL 连接串，形如 postgresql+psycopg://user:password@host:5432/dbname  到时候读取环境变量

    EMBEDDING_DIM:int   # embedding 模型输出维度，pgvector 建列必须固定，需与远端模型一致

    MAX_RETRY_TIMES:int=3   #大模型请求失败最大重试次数


    SIMILARITY_THRESHOLD:float=0.85  #相似度阈值，超过该阈值的记忆将被认为是重复的

    TOP_K:int=3    #搜索记忆时的最大返回条数

    # BM25 参数，写进索引 DDL，改了必须重建索引才生效，不是查询时参数
    BM25_K1:float=1.2   #词频饱和

    BM25_B:float=0.75   #长度归一化

    SIM_TO_THROW:float=0.95  #相似度超过该阈值的记忆将被丢弃，不再存储

    MAX_UNARCHIVED:int=10    #一个会话内未归档的原文最大数量，超过该数量将触发自动归档

    MAX_UNARCHIVED_TIME:int=60*30  #一个会话内未归档的原文最大时间，超过该时间将触发自动归档

    EPISODIC_CONSOLIDATION_INTERVAL:int=60*5  #情景记忆归档的时间间隔，单位秒


    # ---------- RabbitMQ 触发链 ----------
    MQ_HOST:str="127.0.0.1"
    # 不能用 localhost：Windows 上它优先解析成 ::1，而 5672 没听 IPv6，
    # 连上去会静默超时很久（实测 ::1:5672 超时，127.0.0.1:5672 秒连）
    MQ_PORT:int=5672

    MQ_VHOST:str="/MiniMemo"

    MQ_USER:str="MiniMemo"

    MQ_PASSWORD:str=""   #敏感项，默认空，在 .env 里填

    MQ_PREFETCH:int=10   #不能调大：抽取互斥锁是进程内的，prefetch=1 才能保证同一会话不被并发抽两遍

    MQ_RETRY_TTL_MS:int=30000   #重试队列消息存活时间，过期经死信回到主队列

    MQ_MAX_RETRY:int=3   #消息被死信的次数上限，超过则转发进死信队列等人工重放

    MQ_SCAN_INTERVAL:int=60   #兜底扫描间隔，单位秒，必须远小于 MAX_UNARCHIVED_TIME


    negative_words:list[str]=["不", "没", "无", "别", "勿", "非", "未", "莫", "甭", "不要", "没有"]  #负面词汇列表，用于过滤记忆中的负面内容

settings = Settings() # type: ignore