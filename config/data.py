from pathlib import Path
from typing import ClassVar, Literal
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


    SIMILARITY_THRESHOLD:float=0.85  #入库判重阈值，超过该阈值的记忆将被认为是重复的，要送模型复核

    # 检索召回下限，和上面的判重阈值分开：判重宁可漏判也要高，
    # 召回宁可带噪声也要低，两者共用一个值会让向量路几乎召不回任何东西
    # 这个 embedding 空间的相似度尺度整体在 0.6~0.8，取 0.65 时每题约十几条候选
    RECALL_SIMILARITY_THRESHOLD:float=0.65

    TOP_K:int=50    #搜索记忆时的最大返回条数

    # BM25 召回候选数上限，和 TOP_K 分开：RRF 假设各路输入规模相当，排序才有可比性。
    # BM25 用 ||| 任意词命中，语料小的时候很容易一路满候选把 RRF 压成自己一家的排序，
    # 三路向量按阈值筛完只剩个位数，输入差一个量级，等权融合就失衡了
    BM25_CANDIDATE_LIMIT:int=15

    # BM25 参数，写进索引 DDL，改了必须重建索引才生效，不是查询时参数
    BM25_K1:float=1.2   #词频饱和

    BM25_B:float=0.75   #长度归一化

    SIM_TO_THROW:float=0.95  #相似度超过该阈值的记忆将被丢弃，不再存储

    MAX_UNARCHIVED_EPISODIC:int=10    #一个会话内未归档的情景记忆最大数量，超过该数量将触发自动归档

    MAX_UNARCHIVED_SEMANTIC:int=20    #一个会话内未归档的语义记忆最大数量，超过该数量将触发自动归档


    MAX_UNARCHIVED_TIME_EPISODIC:int=60*30  #一个会话内未归档的原文最大时间，超过该时间将触发自动归档

    MAX_UNARCHIVED_TIME_SEMANTIC:int=60*60  #一个agent未归档的语义记忆最大时间，超过该时间将触发自动归档

    getMemoryMode: ClassVar[Literal["episodic", "semantic"]] = "episodic"
    
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

    MAX_SIM_CONCURRENCY :int=5   #相似度判断的最大并发数，过大容易打爆大模型






    #RRF_FUSE工具的权重配置
    RRF_K:int=60   #RRF 融合算法的 k 参数，越大越偏向于多路检索结果的融合，越小越偏向于单路检索结果的排序

    RRF_ORIGINAL_WEIGHT:float=1.0   #原始输入的权重，越大越偏向于原始输入的排序，越小越偏向于多路检索结果的融合

    RRF_EPISODIC_WEIGHT:float=1.0   #情景记忆的权重，越大越偏向于情景记忆的排序，越小越偏向于多路检索结果的融合

    RRF_SEMANTIC_WEIGHT:float=1.0   #语义记忆的权重，越大越偏向于语义记忆的排序，越小越偏向于多路检索结果的融合

    RRF_BM25_WEIGHT:float=1.0   #BM25的权重，越大越偏向于BM25的排序，越小越偏向于多路检索结果的融合






    
    #negative_words:list[str]=["不", "没", "无", "别", "勿", "非", "未", "莫", "甭", "不要", "没有"]  #负面词汇列表，用于过滤记忆中的负面内容

settings = Settings() # type: ignore