import heapq

import numpy as np
from sqlalchemy.orm import Session

from  minimemo.config.data import settings
from  minimemo.models.memoryModel.memory import Memory
from  minimemo.models.memoryVector import memoryVector
from  minimemo.tools import numpyTool


class embeddingRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_vector(self, memory_vectors: list[memoryVector]):
        """
        为指定的智能体添加向量
        """
        for memory_vector in memory_vectors:
            self.session.add(memory_vector)
        self.session.commit()

    def query_vectors(self, query: list[float], agent_id: str, embedding_model: str, memory_type: str | None = None) -> list[memoryVector]:
        """
        查询指定内容相似度最高的前 top_k 条向量
        memory_type 是 memory 表上的鉴别器取值，传了就只在同等级的记忆之间比较，
        不传则不加限制，检索时用（要同时召回情景与语义两路）
        """
        vector_query = self.session.query(memoryVector).join(
            Memory, memoryVector.memory_id == Memory.id
        ).filter(
            memoryVector.agent_id == agent_id,
            memoryVector.embedding_model == embedding_model,
        )
        if memory_type is not None:
            vector_query = vector_query.filter(Memory.memory_type == memory_type)
        vector_list = vector_query.all()
        scored = [
            (
                numpyTool.cosine_similarity(
                    query,v.embedding
                ),
                v,
            )
            for v in vector_list
        ]
        top = heapq.nlargest(settings.TOP_K, scored, key=lambda x: x[0])
        return [v for _, v in top]  # 返回前 top_k 条的 memoryVector 对象列表，按相似度从高到低排序

    def get_all_vectors(self, embedding_model: str) -> list[memoryVector]:
        """
        获取指定模型下的所有向量
        """
        return self.session.query(memoryVector).filter_by(
            embedding_model=embedding_model
        ).all()
