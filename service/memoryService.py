import numpy as np

from common.requestSchema.searchRequest import searchRequest
from common.requestSchema.storeRequest import storeRequest
from config.data import settings
from config.modelConfig import get_pool
from models import originContent, Memory
from repository.embeddingRepository import embeddingRepository
from repository.memoryRepository import memoryRepository
from repository.originContentRepository import originContentRepository
from service.modelService import modelService
from tools.numpyTool import cosine_similarity


class memoryService:

    def __init__(self, memory_repository: memoryRepository, embedding_repository: embeddingRepository, origin_content_repository: originContentRepository):
        self.memory_repository = memory_repository
        self.origin_content_repository = origin_content_repository
        self.embedding_repository = embedding_repository

    def add_memory(self, store_request: storeRequest):
        """
        为指定的智能体添加记忆，这里也是添加记忆的核心逻辑
        """
        # 这里可以实现将记忆存储到数据库或其他存储介质的逻辑

        def _process_similarity(memories:list) -> list:

            def _nagative_common(memory1:str,memory2:str) -> bool:
                """
                负面判断，判断是否有负面内容，如果有则删除
                """
                for negative_word in settings.negative_words:
                    if (negative_word in memory1 and negative_word in memory2) or (negative_word not in memory1 and negative_word not in memory2):
                        return True
                return False

            list_to_remove=[]
            for i in range(len(memories)):
                for j in range(i+1,len(memories)):
                    if memories[i]["embedding"] and memories[j]["embedding"]:
                        similarity=cosine_similarity(memories[i]["embedding"],memories[j]["embedding"])
                        if similarity>settings.SIMILARITY_THRESHOLD and _nagative_common(memories[i]["content"],memories[j]["content"]):
                            list_to_remove.append(j)
            memories = [m for idx, m in enumerate(memories) if idx not in list_to_remove]
            return memories


        kwargs=store_request.additional_kwargs
        origin_content=originContent(agent_id=store_request.agent_id,
                      content=store_request.origin_content,
                      additional_kwargs=store_request.additional_kwargs
                      )
        self.origin_content_repository.add_content(
           origin_content
        )
        origin_content_id=origin_content.id
        model=get_pool()
        chat_model=model.chat
        embedding_model=model.embedding
        memories_list=modelService.chat(origin_content=origin_content.content, model=chat_model, additional_kwargs=kwargs)
        for memory in memories_list:
            embedding=modelService.embedding(memory["content"],embedding_model)
            memory["embedding"]=np.asarray(embedding).astype(np.float32).tobytes()
            memory["embedding_model"]=embedding_model.model_name
        memories_list=_process_similarity(memories_list)  #处理相似内容
        self.memory_repository.add_memory(memories_list,agent_id=store_request.agent_id,origin_content_id=origin_content_id)



    def search_memory(self, search_request:searchRequest) -> list[str]:
        """
        搜索指定智能体的记忆
        """
        model=get_pool()
        embedding_model = model.embedding
        query_embedding=modelService.embedding(search_request.query,embedding_model)
        memory_list=self.memory_repository.search_memory(agent_id=search_request.agent_id,query=query_embedding,embedding_model=embedding_model.model_name)
        return [memory.content for memory in memory_list]





