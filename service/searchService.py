from loguru import logger

from common.requestSchema.searchRequest import searchRequest
from config.modelConfig import modelPool
from models.memoryModel.origin_content import originContent
from repository.embeddingRepository import embeddingRepository
from repository.episodicMemoryRepository import episodicMemoryRepository
from repository.originContentRepository import originContentRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from repository.userRepository import userRepository
from service.modelService import modelService
from tools.BM25Search import bm25_search
from db.session import engine
from config.data import settings





class searchService:
    
    def __init__(
        self,
        semantic_memory_repository: semanticMemoryRepository,
        episodic_memory_repository: episodicMemoryRepository,
        embedding_repository: embeddingRepository,
        origin_content_repository: originContentRepository,
        user_repository: userRepository,
    ):
        self.semantic_memory_repository = semantic_memory_repository
        self.episodic_memory_repository = episodic_memory_repository
        self.origin_content_repository = origin_content_repository
        self.embedding_repository = embedding_repository
        self.user_repository = user_repository



    async def search_origin_content(self, search_request:searchRequest, *, user_id: str) -> list[originContent]:
        """
        检索原文
        原文也是记忆，向量同样挂在 memory_vector 上，
        所以召回路径和 search_memory 完全一样，
        区别只是最后按 origin_content 这个子类去取
        """
        config = await self.user_repository.get_models(user_id)
        model = modelPool(**config.model_dump(exclude_none=True))
        embedding_model = model.embedding
        query_embedding=await modelService.embedding(search_request.query, embedding_model)
        vector_list=await self.embedding_repository.query_vectors(
            agent_id=search_request.agent_id,
            embedding_model=embedding_model.model_name,
            query=,
            memory_type="origin",     # 限制搜索原文
        )
        for vector, _ in vector_list:
            if vector.memory_id not in seen:
                seen.add(vector.memory_id)
                memory_ids.append(vector.memory_id)
        content_list=await self.origin_content_repository.search_memory(memory_ids)
        logger.info(f"检索出来的原文:{[content.content for content in content_list]}")
        return content_list




    @staticmethod
    async def _search_bm25(search_request:searchRequest, *, user_id: str) -> list[str]:
        """
        bm25 检索原始输入
        """
        bm25_result_list=await bm25_search(engine,search_request.query)
        memory_ids:list[str]=[l.memory_id for l in bm25_result_list]
        return memory_ids



    

    
