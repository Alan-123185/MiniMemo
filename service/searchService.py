from typing import Literal
from loguru import logger
from common.memoryInfo import returnMemoryInfo
from common.requestSchema.searchRequest import searchRequest
from config.modelConfig import modelPool
from models.memoryModel.memory import Memory
from repository.embeddingRepository import embeddingRepository
from repository.memoryRepository import memoryRepository
from repository.userRepository import userRepository
from service.modelService import modelService
from tools.BM25Search import bm25_search
from db.session import engine
from config.data import settings
from tools.RRFFuse import rrf_fuse





class searchService:
    
    def __init__(
        self,
        embedding_repository: embeddingRepository,
        memory_repository:memoryRepository,
        user_repository: userRepository,
    ):
        self.memory_respository=memory_repository
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
        seen={}
        for vector, _ in vector_list:
            seen[vector.memory_id]=None
        return list(seen)



    async def pre_ranking(self, search_request:searchRequest) -> list[str]:
        """
        11.15
        对召回的记忆进行粗排 整合几种召回获取的记忆id列表，去重后返回
        还没有着手处理已失效记忆 这个到时候要重点处理
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
        # 3.
        # 11.15 第一版
        #  用 RRF 融合算法融合几路召回结果，得到最终的记忆id列表
        memory_ids=rrf_fuse(
            ranked_lists=[bm25_memory_ids,origin_memory_ids,episodic_memory_ids,semantic_memory_ids],
            k=settings.RRF_K,
            top_n=settings.RRF_TOP_N
        )
        return memory_ids


    """
    11.18
    决定加上重排序进行精排
    """
    async def fine_ranking(self, search_request:searchRequest, memories: list[Memory]) -> list[Memory]:
        user_id = search_request.user_id
        config = await self.user_repository.get_models(user_id)
        model = modelPool(**config.model_dump(exclude_none=True))
        reranker_model = model.reranker
        # 在这里实现重排序逻辑
        if not memories:
            logger.info("No memories to rerank.")
            return memories
        rerank_list=await modelService.rerank(search_request.query,memories, reranker_model)
        #这里可以加上精细化处理


        return rerank_list[search_request.return_count:]





    async def search_memory(self, search_request:searchRequest) -> list[returnMemoryInfo]:
        """
        11.15
        只加pre_ranking的粗排 看看召回效果
        """
        memory_ids=await self.pre_ranking(search_request)
        memory_list=await self.memory_respository.search_memory(memory_ids)
        #这里再补一层重排序
        rerank_list=await self.fine_ranking(search_request=search_request, memories=memory_list)
        return [returnMemoryInfo(content=memory.content,
                                 memory_type=memory.memory_type,
                                 update_time=memory.update_time
                                 ) for memory in rerank_list]



    @staticmethod
    async def _search_bm25(search_request:searchRequest) -> list[str]:
        """
        bm25 检索原始输入
        """
        bm25_result_list=await bm25_search(engine,search_request.query,search_request.agent_id)
        memory_ids:list[str]=[l.memory_id for l in bm25_result_list]
        return memory_ids



    

    
