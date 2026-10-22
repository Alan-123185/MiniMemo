import uuid

import numpy as np
from sqlalchemy.orm import Session
import heapq

from config.data import Settings, settings
from models import Memory
from models.memoryVector import memoryVector
from tools import numpyTool


class memoryRepository:

    def __init__(self,session:Session):
        self.session=session



    def add_memory(self,memories:list[dict],agent_id:str,origin_content_id:str) -> None:
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




    def search_memory(self,agent_id:str,query:list[float],embedding_model:str)-> list[Memory]:
        vector_list=self.session.query(memoryVector).filter_by(agent_id = agent_id , embedding_model = embedding_model).all()
        scored = [
            (numpyTool.cosine_similarity(query, np.frombuffer(v.embedding, dtype=np.float32).tolist()), v)
            for v in vector_list
        ]
        top = heapq.nlargest(settings.TOP_K, scored, key=lambda x: x[0])
        ret=[]
        for score, v in top:
            ret.append(self.session.query(Memory).filter_by(id=v.memory_id).first())
        return ret



