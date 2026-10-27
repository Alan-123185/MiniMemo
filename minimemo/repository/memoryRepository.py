import uuid
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

from minimemo.models.memoryModel.memory import Memory
from  minimemo.models.memoryVector import memoryVector


class memoryRepository(ABC):
    kind:str

    def __init__(self,session:Session):
        self.session=session

    @abstractmethod
    def add_memory(self,memories:list[dict],agent_id:str) -> None:
        ...
        # for memory in memories:
        #     memo=Memory(
        #         id=str(uuid.uuid4()),
        #         content=memory["content"],
        #         agent_id=agent_id,
        #         origin_content_id=origin_content_id,
        #         type=memory["type"],
        #         is_alive=memory["is_alive"]
        #     )
        #     self.session.add(memo)
        #     memory_id=memo.id
        #     self.session.add(memoryVector(memory_id=memory_id,
        #                                   embedding=memory["embedding"],
        #                                   embedding_model=memory["embedding_model"],
        #                                   agent_id=agent_id
        #                                   ))
        # self.session.commit()



    @abstractmethod
    def search_memory(self,vector_list:list[str])-> list[Memory]:
        ...
        # #根据向量列表查找记忆
        # #多路查询之后  顺序没有意义
        # ret= self.session.query(Memory).filter(Memory.id.in_(vector_list),Memory.is_alive==True).all()
        # return ret


    @abstractmethod
    def remove_memory(self, memory_id:str) -> None:
        ...
        # self.session.query(Memory).filter(Memory.id==memory_id).delete()
        # self.session.query(memoryVector).filter(memoryVector.memory_id==memory_id).delete()
        # self.session.commit()

    @abstractmethod
    def kill_memory(self, memory_id:str) -> None:
        ...
        #标记记忆为死亡
        # self.session.query(Memory).filter(Memory.id==memory_id).update({"is_alive":False})
        # self.session.commit()

    """
    这个方法用来更新记忆的内容和向量  在大模型判定update记忆之后调用
    """
    @abstractmethod
    def update_memory(self, memory_id:str, content:str,new_embedding:bytes) -> None:
        ...
        # self.session.query(Memory).filter(Memory.id==memory_id).update({"content":content})
        # self.session.query(memoryVector).filter(memoryVector.memory_id==memory_id).update({"embedding":new_embedding})
        # self.session.commit()





