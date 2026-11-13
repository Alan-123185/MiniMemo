import asyncio
from loguru import logger
from common.memoryInfo import originContentMemoryInfo
from  common.requestSchema.searchRequest import searchRequest
from common.requestSchema.storeRequest import originContentStoreRequest
from  config.modelConfig import get_pool
from models.memoryModel.memory import Memory
from mq.publisher import get_publisher
from prompt.memoryPromptHEAD import MEMORY_PROMPT_HEAD
from  repository.embeddingRepository import embeddingRepository
from repository.episodicMemoryRepository import episodicMemoryRepository
from  repository.originContentRepository import originContentRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from  service.modelService import modelService
from tools.backgroundTask import spawn


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
            embedding=embedding,
            embedding_model=embedding_model.model_name,
            role=store_request.role,
            session_id=store_request.session_id
        )
        await self.origin_content_repository.add_memory([memory], agent_id=store_request.agent_name)
        """
        11.9
        添加完原始内容之后你不要触发情景记忆 
        """

       

    """
    10.31
    这个函数到时候需要重写 现在是未重构之前的结构 先不管
    11.13
    制定记忆搜索召回策略
    这是记忆召回最终直接调用的函数
       情景记忆、语义记忆分别做向量与关键词召回，统一融合后，再判断哪些记忆真正有助于回答当前问题。
    """
    async def search_memory(self, search_request:searchRequest) -> list[Memory]:
        """
        搜索指定智能体的记忆
        """
        model=get_pool()
        embedding_model = model.embedding
        question=await modelService.sort_question(search_request.query,model=model.chat)
        """
        多路查询之后，去重，然后组成向量列表，传给 repository 去查询
        每个 query 都会召回一批向量，这里按召回顺序汇总 memory_id 并去重，
        顺序本身代表了相似度高低，不能打乱
        """
        memory_ids:list[str]=[]
        seen:set[str]=set()
        for q in question:
            query_embedding=await asyncio.to_thread(modelService.embedding,q,embedding_model)
            vector_list=await self.embedding_repository.query_vectors(
                agent_id=search_request.agent_name,
                embedding_model=embedding_model.model_name,query=query_embedding)
            for vector, _ in vector_list:
                if vector.memory_id not in seen:
                    seen.add(vector.memory_id)
                    memory_ids.append(vector.memory_id)
        episodic_memory_list=await self.episodic_memory_repository.search_memory(memory_ids)
        semantic_memory_list=await self.semantic_memory_repository.search_memory(memory_ids)
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
        question=await modelService.sort_question(search_request.query,model=model.chat)
        memory_ids:list[str]=[]
        seen:set[str]=set()
        for q in question:
            query_embedding=await asyncio.to_thread(modelService.embedding,q,embedding_model)
            vector_list=await self.embedding_repository.query_vectors(
                agent_id=search_request.agent_name,
                embedding_model=embedding_model.model_name,
                query=query_embedding,
                memory_type="origin",  # 限制搜索原文
            )
            for vector, _ in vector_list:
                if vector.memory_id not in seen:
                    seen.add(vector.memory_id)
                    memory_ids.append(vector.memory_id)
        content_list=await self.origin_content_repository.search_memory(memory_ids)
        logger.info(f"检索出来的原文:{[content.content for content in content_list]}")
        return content_list


