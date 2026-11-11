from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from  minimemo.config.data import settings
from  minimemo.models.memoryModel.memory import Memory
from  minimemo.models.memoryVector import memoryVector


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

    async def query_vectors(self, query: list[float], agent_id: str, embedding_model: str, memory_type: str | None = None) -> Sequence[memoryVector]:
        """
        查询指定内容相似度最高的前 top_k 条向量，按相似度从高到低排序
        memory_type 是 memory 表上的鉴别器取值，传了就只在同等级的记忆之间比较，
        不传则不加限制，检索时用（要同时召回情景与语义两路）

        embedding 是 vector 列，用 pgvector 的余弦距离在库里排序取前 k，
        不再把整个 agent 的向量全拉回内存算
        """
        vector_query = select(memoryVector).join(
            Memory, memoryVector.memory_id == Memory.id
        ).where(
            memoryVector.agent_id == agent_id,
            memoryVector.embedding_model == embedding_model,
        )
        if memory_type is not None:
            vector_query = vector_query.where(Memory.memory_type == memory_type)
        # cosine_distance 就是 <=>，值越小越相似，与相似度方向相反，所以升序
        return (await self.session.execute(
            vector_query.order_by(
                memoryVector.embedding.cosine_distance(query)    #直接让pgsql内部计算
            ).limit(settings.TOP_K)
        )).scalars().all()

    async def get_all_vectors(self, embedding_model: str) -> Sequence[memoryVector]:
        """
        获取指定模型下的所有向量
        """
        return (await self.session.execute(
            select(memoryVector).filter_by(embedding_model=embedding_model)
        )).scalars().all()
