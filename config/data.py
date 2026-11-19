from pathlib import Path
from typing import ClassVar, Literal
from pydantic_settings import BaseSettings

ENV_FILE=Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}

    DEFAULT_BASE_URL:str=""

    DEFAULT_MODEL:str=""

    DEFAULT_API_KEY:str=""

    DEFAULT_RERANKER_MODEL:str=""

    DEFAULT_EMBEDDING_MODEL:str=""

    DB_DSN:str=""   # PostgreSQL 连接串，形如 postgresql+psycopg://user:password@host:5432/dbname  到时候读取环境变量

    EMBEDDING_DIM:int   # embedding 模型输出维度，pgvector 建列必须固定，需与远端模型一致

    MAX_RETRY_TIMES:int=3   #大模型请求失败最大重试次数


    SIMILARITY_THRESHOLD:float=0.85  #入库判重阈值，超过该阈值的记忆将被认为是重复的，要送模型复核

    # 检索召回下限，三路分开配。余弦相似度和文本长度强相关：语义记忆平均 34 字，
    # 余弦天然偏高；情景记忆平均 241 字的叙述，余弦天然偏低。
    # 三路共用一个数就等于默认它们在同一尺度上，实际不是
    RECALL_SIMILARITY_THRESHOLD_ORIGIN:float=0.56     #原文，平均 171 字

    RECALL_SIMILARITY_THRESHOLD_EPISODIC:float=0.52   #情景记忆，平均 241 字

    RECALL_SIMILARITY_THRESHOLD_SEMANTIC:float=0.65   #语义记忆，平均 34 字

    TOP_K:int=50    #不带 memory_type 的向量查询的候选上限，判重显式传这个值

    # RRF 融合后取多少条，这里才是「搜索返回几条」。和候选上限不是一回事：
    # 三路配额 RECALL_CANDIDATE_LIMIT_* 决定进融合的原料，这个决定出锅的份量
    # 这个暂时先不动，到时候再改
    RRF_TOP_N:int=25

    # BM25 召回候选数上限，和 TOP_K 分开：RRF 假设各路输入规模相当，排序才有可比性。
    # BM25 任意词命中，语料小的时候很容易一路满候选把 RRF 压成自己一家的排序，
    # 三路向量按阈值筛完只剩个位数，输入差一个量级，等权融合就失衡了
    BM25_CANDIDATE_LIMIT:int=15

    # 三路向量各自的召回候选上限，和 TOP_K 分开：每条路只负责自己那一类记忆，
    # 配额按各类型的饱和度定——origin 给到 20 条就把自己那类召全，episodic 7、semantic 3 同理。
    # 给多了不涨召回，只是把无关记忆塞进候选并集，挤掉 RRF 融合的位子
    RECALL_CANDIDATE_LIMIT_ORIGIN:int=20

    RECALL_CANDIDATE_LIMIT_EPISODIC:int=7

    RECALL_CANDIDATE_LIMIT_SEMANTIC:int=3

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

    SEARCH_RETURN_K:int=25   #最终搜索返回的记忆数量

    DEFAULT_RETURN_K:int=10   #默认搜索返回的记忆数量

    
    #negative_words:list[str]=["不", "没", "无", "别", "勿", "非", "未", "莫", "甭", "不要", "没有"]  #负面词汇列表，用于过滤记忆中的负面内容

settings = Settings() # type: ignore