import numpy as np
from common.requestSchema.storeRequest import storeRequest
from config.data import settings
from config.modelConfig import get_pool
from models import  originContent
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
            list_to_remove=[]
            for i in range(len(memories)):
                for j in range(i+1,len(memories)):
                    if memories[i]["embedding"] and memories[j]["embedding"]:
                        similarity=cosine_similarity(memories[i]["embedding"],memories[j]["embedding"])
                        if similarity>settings.SIMILARITY_THRESHOLD:
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
        memories_list=_process_similarity(memories_list)  #处理相似内容
        self.memory_repository.add_memory(memories_list,agent_id=store_request.agent_id,origin_content_id=origin_content_id)








