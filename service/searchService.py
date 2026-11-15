from typing import Literal
from common.requestSchema.searchRequest import searchRequest
from config.modelConfig import modelPool
from repository.embeddingRepository import embeddingRepository
from repository.episodicMemoryRepository import episodicMemoryRepository
from repository.originContentRepository import originContentRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from repository.userRepository import userRepository
from service.modelService import modelService
from tools.BM25Search import bm25_search
from db.session import engine





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





    async def _search_memory_L1(self, search_request:searchRequest,query_embedding:list[float],mode=Literal["origin","episodic","semantic"]) -> list[str]:
        """
        根据查询类型搜索向量相似度，返回记忆id列表 复用向量需要外部计算
        """
        config = await self.user_repository.get_models(search_request.user_id)
        model = modelPool(**config.model_dump(exclude_none=True))
        embedding_model = model.embedding
        vector_list=await self.embedding_repository.query_vectors(
            agent_id=search_request.agent_id,
            embedding_model=embedding_model.model_name,
            query=query_embedding,
            memory_type=mode,     # 限制搜索原文 # type: ignore
        )
        seen=set()
        for vector, _ in vector_list:
            seen.add(vector.memory_id)
        return list(seen)

    
    async def search_memory(self, search_request:searchRequest) -> list[str]:
        """
        搜索指定智能体的记忆
        """
        user_id=search_request.user_id
        config = await self.user_repository.get_models(user_id)
        model = modelPool(**config.model_dump(exclude_none=True))
        embedding_model=model.embedding
        query_embedding=await modelService.embedding(search_request.query,embedding_model)
        # 1. bm25 检索原始输入
        bm25_memory_ids=await self._search_bm25(search_request)
        # 2. 向量检索原文、情景记忆、语义记忆
        origin_memory_ids=await self._search_memory_L1(search_request,query_embedding,"origin")
        episodic_memory_ids=await self._search_memory_L1(search_request,query_embedding,"episodic")
        semantic_memory_ids=await self._search_memory_L1(search_request,query_embedding,"semantic")
        # 3. 融合结果
        memory_ids=list(set(bm25_memory_ids+origin_memory_ids+episodic_memory_ids+semantic_memory_ids))
        return memory_ids



    






    @staticmethod
    async def _search_bm25(search_request:searchRequest) -> list[str]:
        """
        bm25 检索原始输入
        """
        bm25_result_list=await bm25_search(engine,search_request.query)
        memory_ids:list[str]=[l.memory_id for l in bm25_result_list]
        return memory_ids



    

    
