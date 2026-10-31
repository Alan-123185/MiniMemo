import asyncio
import numpy as np
from loguru import logger
from minimemo.common.memoryInfo import memoryInfo, originContentMemoryInfo
from  minimemo.common.requestSchema.searchRequest import searchRequest
from minimemo.common.requestSchema.storeRequest import originContentStoreRequest
from  minimemo.config.modelConfig import get_pool
from minimemo.models.memoryModel.memory import Memory
from minimemo.prompt.memoryPromptHEAD import MEMORY_PROMPT_HEAD
from  minimemo.repository.embeddingRepository import embeddingRepository
from minimemo.repository.episodicMemoryRepository import episodicMemoryRepository
from  minimemo.repository.originContentRepository import originContentRepository
from minimemo.repository.semanticMemoryRepository import semanticMemoryRepository
from minimemo.service.consolidationService import consolidationService
from  minimemo.service.modelService import modelService
from minimemo.tools.backgroundTask import spawn


class memoryService:

    def __init__(self, semantic_memory_repository:semanticMemoryRepository,episodic_memory_repository:episodicMemoryRepository, embedding_repository: embeddingRepository, origin_content_repository: originContentRepository):
        self.semantic_memory_repository = semantic_memory_repository
        self.episodic_memory_repository = episodic_memory_repository
        self.origin_content_repository = origin_content_repository
        self.embedding_repository = embedding_repository


    """
    添加第一层记忆  原始内容
    """
    async def add_origin_content(self, store_request: originContentStoreRequest):
        """
        为指定的智能体添加原始内容，非常简陋
        """
        model=get_pool()
        embedding_model=model.embedding
        embedding=await asyncio.to_thread(modelService.embedding,store_request.origin_content,embedding_model)
        memory=originContentMemoryInfo(
            content=store_request.origin_content,
            embedding=np.asarray(embedding).astype(np.float32).tobytes(),
            embedding_model=embedding_model.model_name,
            role=store_request.role,
            session_id=store_request.session_id
        )
        self.origin_content_repository.add_memory([memory],agent_id=store_request.agent_id)
        spawn(consolidationService.episodic_memory_L1(store_request))



       

    """
    10.31
    这个函数到时候需要重写 现在是未重构之前的结构 先不管
    """
    async def search_memory(self, search_request:searchRequest) -> list[Memory]:
        """
        搜索指定智能体的记忆
        """
        model=get_pool()
        embedding_model = model.embedding
        question=modelService.sort_question(search_request.query,model=model.chat)
        """
        多路查询之后，去重，然后组成向量列表，传给 repository 去查询
        每个 query 都会召回一批向量，这里按召回顺序汇总 memory_id 并去重，
        顺序本身代表了相似度高低，不能打乱
        """
        memory_ids:list[str]=[]
        seen:set[str]=set()
        for q in question:
            query_embedding=await asyncio.to_thread(modelService.embedding,q,embedding_model)
            vector_list=self.embedding_repository.query_vectors(
                agent_id=search_request.agent_id,
                embedding_model=embedding_model.model_name,query=query_embedding)
            for vector in vector_list:
                if vector.memory_id not in seen:
                    seen.add(vector.memory_id)
                    memory_ids.append(vector.memory_id)
        episodic_memory_list=self.episodic_memory_repository.search_memory(memory_ids)
        semantic_memory_list=self.semantic_memory_repository.search_memory(memory_ids)
        # 两路召回的顺序由 memory_ids 决定，这里统一按 memory_ids 重排一次
        merged={memory.id:memory for memory in episodic_memory_list+semantic_memory_list}
        memory_list=[merged[memory_id] for memory_id in memory_ids if memory_id in merged]
        logger.info(f"检索出来的记忆:{[memory.content for memory in memory_list]}")
        return memory_list


    async def search_origin_content(self, search_request:searchRequest) -> list:
        """
        检索原文
        原文也是记忆，向量同样挂在 memory_vector 上，
        所以召回路径和 search_memory 完全一样，
        区别只是最后按 origin_content 这个子类去取
        """
        model=get_pool()
        embedding_model = model.embedding
        question=modelService.sort_question(search_request.query,model=model.chat)
        memory_ids:list[str]=[]
        seen:set[str]=set()
        for q in question:
            query_embedding=await asyncio.to_thread(modelService.embedding,q,embedding_model)
            vector_list=self.embedding_repository.query_vectors(
                agent_id=search_request.agent_id,
                embedding_model=embedding_model.model_name,
                query=query_embedding,
                memory_type="origin",  # 限制搜索原文
            )
            for vector in vector_list:
                if vector.memory_id not in seen:
                    seen.add(vector.memory_id)
                    memory_ids.append(vector.memory_id)
        content_list=self.origin_content_repository.search_memory(memory_ids)
        logger.info(f"检索出来的原文:{[content.content for content in content_list]}")
        return content_list


    #自动装载记忆
    async def load_memory(self, search_request:searchRequest) -> str:
        """
        加载指定智能体的所有记忆
        """
        memory_list=await self.search_memory(search_request)
        return MEMORY_PROMPT_HEAD+"\n".join([memory.content for memory in memory_list])

