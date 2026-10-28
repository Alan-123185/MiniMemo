import asyncio
import numpy as np
from loguru import logger
from minimemo.common.existFact import existFact
from  minimemo.common.requestSchema.searchRequest import searchRequest
from minimemo.common.requestSchema.storeRequest import storeRequest, episodeStoreRequest
from  minimemo.config.data import settings
from  minimemo.config.modelConfig import get_pool
from minimemo.models import originContent
from minimemo.models.memoryModel.memory import Memory
from minimemo.prompt.memoryPromptHEAD import MEMORY_PROMPT_HEAD

from  minimemo.repository.embeddingRepository import embeddingRepository
from minimemo.repository.episodicMemoryRepository import episodicMemoryRepository
from  minimemo.repository.originContentRepository import originContentRepository
from minimemo.repository.semanticMemoryRepository import semanticMemoryRepository
from  minimemo.service.modelService import modelService
from  minimemo.tools.numpyTool import cosine_similarity


class memoryService:

    def __init__(self, semantic_memory_repository:semanticMemoryRepository,episodic_memory_repository:episodicMemoryRepository, embedding_repository: embeddingRepository, origin_content_repository: originContentRepository):
        self.semantic_memory_repository = semantic_memory_repository
        self.episodic_memory_repository = episodic_memory_repository
        self.origin_content_repository = origin_content_repository
        self.embedding_repository = embedding_repository

    async def add_semantic_memory(self, store_request: storeRequest):
        """
        为指定的智能体添加记忆，这里也是添加记忆的核心逻辑
        10.27
        这个方法暂时只能添加情景记忆 无法添加语义记忆 先不管
        TODO: 需要添加语义记忆的逻辑
        """
        # 这里可以实现将记忆存储到数据库或其他存储介质的逻辑

        async def _process_similarity(memories:list) -> list:

            """
            10.25
            我突然觉得这些策略不是很合理
            """
            # async def _negative_common(memory1:str,memory2:str) -> bool:
            #     """
            #     负面判断，判断是否有负面内容，如果有则删除
            #     """
            #     for negative_word in settings.negative_words:
            #         if (negative_word in memory1 and negative_word not in memory2) or (negative_word not in memory1 and negative_word in memory2):
            #             return False
            #     return True
            #
            # list_to_remove=[]
            # for i in range(len(memories)):
            #     for j in range(i+1,len(memories)):
            #         if memories[i]["embedding"] and memories[j]["embedding"]:
            #             similarity=cosine_similarity(memories[i]["embedding"],memories[j]["embedding"])
            #             if similarity>settings.SIMILARITY_THRESHOLD :
            #                 list_to_remove.append(j)

            #             memories = [m for idx, m in enumerate(memories) if idx not in list_to_remove]

            # 用 id 记录待丢弃的记忆，dict 不可哈希不能直接放进 set
            list_should_remove:set[int] = set()
            for index,memo in enumerate(memories):
                need_to_judge = []
                vector_list=self.embedding_repository.query_vectors(agent_id=store_request.agent_id,embedding_model=memo["embedding_model"],query=memo["embedding"])
                for vector in vector_list:
                    similarity = cosine_similarity(vector.embedding, memo["embedding"])
                    if similarity>=settings.SIM_TO_THROW:
                        # 如果相似度超过阈值，则从记忆列表中移除该记忆
                        list_should_remove.add(index)
                        break
                    elif settings.SIMILARITY_THRESHOLD <= similarity < settings.SIM_TO_THROW:
                        # 如果相似度在阈值范围内，交给大模型判断
                        need_to_judge.append(vector)
                if need_to_judge:
                   memo_list=self.episodic_memory_repository.search_memory([need.memory_id for need in need_to_judge])
                   pan_dict= modelService.judge_similarity(fact1=memo["content"],fact2=[existFact(content=m.content, memory_id=m.id) for m in memo_list], model=get_pool().chat)
                   #评测逻辑
                   if pan_dict["action"] == "ADD":
                       pass
                   elif pan_dict["action"] == "UPDATE":
                       target=pan_dict["target_id"]
                       self.episodic_memory_repository.update_memory(memory_id=target, content=memo["content"], new_embedding=memo["embedding"])
                       list_should_remove.add(index)
                   elif pan_dict["action"] == "DELETE":
                       target=pan_dict["target_id"]
                       self.episodic_memory_repository.kill_memory(memory_id=target)
                   elif pan_dict["action"] == "NONE":
                       list_should_remove.add(index)

            return [m for idx, m in enumerate(memories) if idx not in list_should_remove]

        kwargs=store_request.additional_kwargs
        origin_content=originContent(
                      agent_id=store_request.agent_id,
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
        memories_list=await asyncio.to_thread(modelService.to_memory,origin_content=origin_content.content, model=chat_model, additional_kwargs=kwargs)
        for memory in memories_list:
            embedding=await asyncio.to_thread(modelService.embedding,memory["content"],embedding_model)
            memory["embedding"]=np.asarray(embedding).astype(np.float32).tobytes()
            memory["embedding_model"]=embedding_model.model_name
        memories_list=await _process_similarity(memories_list)  #处理相似内容
        self.episodic_memory_repository.add_memory(memories_list,agent_id=store_request.agent_id,origin_content_id=origin_content_id)



    async def add_episodic_memory(self, store_request:episodeStoreRequest):
        """
        添加情景记忆   无脑添加原文消息
        """
        #这个存的本来是原文，所以不需要存origin_content了
        model=get_pool()
        embedding_model=model.embedding
        self.episodic_memory_repository.add_memory([{"content":store_request.origin_content,"embedding":embedding,"embedding_model":embedding_model.model_name}],agent_id=store_request.agent_id,origin_content_id=origin_content_id)




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
            vector_list=self.embedding_repository.query_vectors(agent_id=search_request.agent_id,embedding_model=embedding_model.model_name,query=query_embedding)
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


    #自动装载记忆
    async def load_memory(self, search_request:searchRequest) -> str:
        """
        加载指定智能体的所有记忆
        """
        memory_list=await self.search_memory(search_request)
        return MEMORY_PROMPT_HEAD+"\n".join([memory.content for memory in memory_list])
