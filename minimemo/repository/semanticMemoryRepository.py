import uuid
from minimemo.models import memoryVector
from minimemo.models.memoryModel.memory import Memory
from minimemo.models.memoryModel.semanticMemory import semanticMemory
from minimemo.repository.memoryRepository import memoryRepository


class semanticMemoryRepository(memoryRepository):
    def kill_memory(self, memory_id: str) -> None:
        self.session.query(semanticMemory).filter(semanticMemory.id==memory_id).update({"is_alive": False})
        self.session.commit()

    def remove_memory(self, memory_id: str) -> None:
        pass

    kind="semantics"


    def add_memory(self,memories:list[dict],agent_id:str) -> None:
        for memory in memories:
            memo = semanticMemory(
                id=str(uuid.uuid4()),
                content=memory["content"],
                agent_id=agent_id,
                is_alive=memory["is_alive"],
            )
            self.session.add(memo)
            memory_id = memo.id
            self.session.add(memoryVector(memory_id=memory_id,
                                          embedding=memory["embedding"],
                                          embedding_model=memory["embedding_model"],
                                          agent_id=agent_id
                                          ))
        self.session.commit()



    def search_memory(self,vector_list: list[str]) -> list[Memory]:
        memory_vectors = self.session.query(memoryVector).filter(memoryVector.id.in_(vector_list)).all()
        memory_ids = [v.memory_id for v in memory_vectors]
        memories = self.session.query(semanticMemory).filter(semanticMemory.id.in_(memory_ids)).all()
        return memories



    def update_memory(self, memory_id: str, content: str, new_embedding: bytes) -> None:
        self.session.query(semanticMemory).filter(semanticMemory.id==memory_id).update({"content":content})
        self.session.query(memoryVector).filter(memoryVector.memory_id==memory_id).update({"embedding":new_embedding})
        self.session.commit()


