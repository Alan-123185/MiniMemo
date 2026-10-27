import uuid

from minimemo.models import memoryVector
from minimemo.models.memoryModel.episodicMemory import episodicMemory
from minimemo.models.memoryModel.memory import Memory
from minimemo.repository.memoryRepository import memoryRepository


class episodicMemoryRepository(memoryRepository):
    kind="episodes"

    def add_memory(self,memories:list[dict],agent_id:str,origin_content_id:str|None=None) -> None:
        for memory in memories:
            memo=episodicMemory(
                id=str(uuid.uuid4()),
                content=memory["content"],
                agent_id=agent_id,
                origin_content_id=origin_content_id,
            )
            self.session.add(memo)
            memory_id=memo.id
            self.session.add(memoryVector(memory_id=memory_id,
                                          embedding=memory["embedding"],
                                          embedding_model=memory["embedding_model"],
                                          agent_id=agent_id
                                          ))
        self.session.commit()

    """
    这个方法只提供向量检索
    """
    def search_memory(self,vector_list:list[str]) -> list[Memory]:
        """
        查询指定内容相似度最高的前3条记忆
        """
        memory_vectors = self.session.query(memoryVector).filter(memoryVector.id.in_(vector_list)).all()
        memory_ids = [v.memory_id for v in memory_vectors]
        memories = self.session.query(episodicMemory).filter(episodicMemory.id.in_(memory_ids)).all()
        return memories

    def update_memory(self, memory_id: str, content: str, new_embedding: bytes) -> None:
        self.session.query(episodicMemory).filter(episodicMemory.id==memory_id).update({"content":content})
        self.session.query(memoryVector).filter(memoryVector.memory_id==memory_id).update({"embedding":new_embedding})
        self.session.commit()
