from sqlalchemy.orm import Session


class memoryRepository:

    def __init__(self,session:Session):
        self.session=session


    def add_memory(self):
        pass