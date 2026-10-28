import heapq

import numpy as np
from sqlalchemy.orm import Session

from  minimemo.config.data import settings
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

    def query_vectors(self, query: list[float], agent_id: str, embedding_model: str) -> list[memoryVector]:
        """
        查询指定内容相似度最高的前 top_k 条向量
        """
        vector_list = self.session.query(memoryVector).filter_by(
            agent_id=agent_id, embedding_model=embedding_model
        ).all()
        scored = [
            (
                numpyTool.cosine_similarity(
                    query, np.frombuffer(v.embedding, dtype=np.float32).tolist()
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
