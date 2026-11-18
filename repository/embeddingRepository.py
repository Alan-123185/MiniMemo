from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from  config.data import settings
from  models.memoryModel.memory import Memory
from  models.memoryVector import memoryVector

"""
11.18
我认为废除各分路阈值才是破局的办法
"""
# 召回阈值按记忆类型分流，调用方不传 similarity_threshold 时用这张表
# _RECALL_THRESHOLD = {
#     "origin": settings.RECALL_SIMILARITY_THRESHOLD_ORIGIN,
#     "episodic": settings.RECALL_SIMILARITY_THRESHOLD_EPISODIC,
#     "semantic": settings.RECALL_SIMILARITY_THRESHOLD_SEMANTIC,
# }

# 召回条数按记忆类型分流，每路只取自己那一类，配额见 config/data.py 的
# RECALL_CANDIDATE_LIMIT_*。不带 memory_type 的调用（判重那条路）不走这张表，仍按 TOP_K 取
_RECALL_LIMIT = {
    "origin": settings.RECALL_CANDIDATE_LIMIT_ORIGIN,
    "episodic": settings.RECALL_CANDIDATE_LIMIT_EPISODIC,
    "semantic": settings.RECALL_CANDIDATE_LIMIT_SEMANTIC,
}


class embeddingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_vector(self, memory_vectors: list[memoryVector]):
        """
        为指定的智能体添加向量
        """
        for memory_vector in memory_vectors:
            self.session.add(memory_vector)
        await self.session.commit()

    async def query_vectors(
        self,
        query: list[float],
        agent_id: str,
        embedding_model: str,
        memory_type: str | None = None,
        #similarity_threshold: float | None = None,
    ) -> list[tuple[memoryVector, float]]:
        """
        查询相似度不低于阈值的前 top_k 条向量，按相似度从高到低排序
        memory_type 是 memory 表上的鉴别器取值，传了就只在同等级的记忆之间比较，
        不传则不加限制，检索时用（要同时召回情景与语义两路）
        similarity_threshold 是余弦相似度下限，低于该值的结果不会返回。
        不传就按 memory_type 取召回阈值（三路分开配，见 config/data.py 的
        RECALL_SIMILARITY_THRESHOLD_*）：召回时传进来的 query 是一句没针对性的
        问句，和三类记忆的长度尺度差得远，得按类型分别放行；判重时传进来的是
        同层级记忆自己的向量，两边同一个尺度，那里显式传 SIMILARITY_THRESHOLD

        embedding 是 vector 列，用 pgvector 的余弦距离在库里排序取前 k，
        不再把整个 agent 的向量全拉回内存算

        返回值第二项是余弦相似度（1 - 余弦距离），由 pgvector 顺带算好一起带回来，
        调用方不必再把向量拉回内存重算一遍
        """
        distance = memoryVector.embedding.cosine_distance(query)    #直接让pgsql内部计算
        vector_query = select(memoryVector, distance).join(
            Memory, memoryVector.memory_id == Memory.id
        ).where(
            memoryVector.agent_id == agent_id,
            memoryVector.embedding_model == embedding_model,
        )
        if memory_type is not None:
            vector_query = vector_query.where(Memory.memory_type == memory_type)
        # if similarity_threshold is None:
        #     similarity_threshold = _RECALL_THRESHOLD.get(memory_type or "")
        #     if similarity_threshold is None:
        #         # 没限定类型时取最松的一路，别在这里丢候选
        #         similarity_threshold = min(_RECALL_THRESHOLD.values())
        # cosine_distance 就是 <=>，相似度 = 1 - distance，值越小越相似。
        # vector_query = vector_query.where(
        #     distance <= 1.0 - similarity_threshold
        # )
        rows = (await self.session.execute(
            vector_query.order_by(distance).limit(
                _RECALL_LIMIT.get(memory_type or "", settings.TOP_K)
            )
        )).all()
        return [(vector, 1.0 - dist) for vector, dist in rows]




    async def get_all_vectors(self, embedding_model: str) -> Sequence[memoryVector]:
        """
        获取指定模型下的所有向量
        """
        return (await self.session.execute(
            select(memoryVector).filter_by(embedding_model=embedding_model)
        )).scalars().all()
