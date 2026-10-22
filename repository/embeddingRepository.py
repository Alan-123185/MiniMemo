
from sqlalchemy.orm import Session

from models.memoryVector import memoryVector


class embeddingRepository:
    def __init__(self,session:Session):
        self.session=session



    def add_vector(self,memory_vectors:list[memoryVector]):
        """
        为指定的智能体添加向量
        """
        for memory_vector in memory_vectors:
            self.session.add(memory_vector)
        self.session.commit()


    def query_vectors(self,agent_id:str,embedding_model:str)-> list[memoryVector]:
        """
        查询指定智能体的向量
        """
        return self.session.query(memoryVector).filter_by(agent_id = agent_id , embedding_model = embedding_model).all()