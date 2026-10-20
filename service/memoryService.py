from repository.memoryRepository import memoryRepository
from repository.originContentRepository import originContentRepository


class memoryService:



    def __init__(self,memory_repository: memoryRepository,origin_content_repository: originContentRepository):
        self.memory_repository = memory_repository
        self.origin_content_repository = origin_content_repository



    def add_memory(self, agent_id: str,origin_content:str):
        """
        为指定的智能体添加记忆，这里也是添加记忆的核心逻辑
        """
        # 这里可以实现将记忆存储到数据库或其他存储介质的逻辑
        self.origin_content_repository.add_content(agent_id, origin_content)









