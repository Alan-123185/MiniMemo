import uuid

from sqlalchemy.orm import Session

from models import Memory
from models.memoryVector import memoryVector


class memoryRepository:

    def __init__(self,session:Session):
        self.session=session



    def add_memory(self,memories:list[dict],agent_id:str,origin_content_id:str) -> None:
        for memory in memories:
            memo=Memory(
                id=str(uuid.uuid4()),
                content=memory["content"],
                agent_id=agent_id,
                origin_content_id=origin_content_id
            )
            self.session.add(memo)
            memory_id=memo.id
            self.session.add(memoryVector(memory_id=memory_id,embedding=memory["embedding"]))
        self.session.commit()