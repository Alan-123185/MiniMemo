import uuid
from sqlalchemy.orm import Session
from  minimemo.models import Memory
from  minimemo.models.memoryVector import memoryVector


class memoryRepository:

    def __init__(self,session:Session):
        self.session=session



    def add_memory(self,memories:list[dict],agent_id:str,origin_content_id:str|None=None) -> None:
        for memory in memories:
            memo=Memory(
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




    def search_memory(self,vector_list:list[memoryVector])-> list[Memory]:
        #根据向量列表查找记忆
        ids=[v.memory_id for v in vector_list]
        ret= self.session.query(Memory).filter(Memory.id.in_(ids)).all()
        by_id = {m.id: m for m in ret}
        return [by_id[v.memory_id] for v in vector_list if v.memory_id in by_id]



    def remove_memory(self, memory_id:str) -> None:
        #删除记忆
        self.session.query(Memory).filter(Memory.id==memory_id).delete()
        self.session.query(memoryVector).filter(memoryVector.memory_id==memory_id).delete()
        self.session.commit()




