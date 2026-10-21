from sqlalchemy.orm import Session

from common.requestSchema.storeRequest import storeRequest


class originContentRepository:
    def __init__(self,session:Session):
        self.session = session

    def add_content(self,store_request:storeRequest):
        """
        为指定的智能体添加原始内容
        """
        # 这里可以实现将原始内容存储到数据库或其他存储介质的逻辑
        self.session.add(store_request)
        self.session.commit()
