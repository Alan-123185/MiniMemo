import asyncio
import numpy as np
from loguru import logger
from minimemo.common.existFact import existFact
from  minimemo.common.requestSchema.searchRequest import searchRequest
from minimemo.common.requestSchema.storeRequest import originContentStoreRequest,storeRequest,episodeStoreRequest
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
        memory={
            "content":store_request.origin_content,
            "embedding":np.asarray(embedding).astype(np.float32).tobytes(),
            "embedding_model":embedding_model.model_name,
            "role":store_request.role,
            "session_id":store_request.session_id
        }
        self.origin_content_repository.add_memory([memory],agent_id=store_request.agent_id)




    """
    治理添加情景记忆的策略

    10.29 
    - 条数水位：同一 agent 攒够 N 条未抽取原文（N 取 6~12，看你的对话密度）
    - 时间水位：距最后一条原文超过 T 分钟（10~30 分钟），说明这段对话告一段落
    - 显式水位：调用方主动说「这里结束了一段」
    - 上限保护：未抽取原文攒到 M 条（比如 50）强制抽一次，兜住长期不触发的极端情况
    """
    async def add_episodeic_memory(self, store_request: episodeStoreRequest):
        """
        10.29
        暂时先写个函数
        这个方法用于按批处理添加情景记忆 
        TODO: 需要制定添加情景记忆和语义记忆的策略和时机
        """

        async def _process_similarity(memories:list) -> list:
            """
            10.25
            我突然觉得这些策略不是很合理
            """
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
        #因为参数传入是多态访问的，这里直接用 store_request 的 additional_kwargs 就行，episodeStoreRequest 也有这个属性
        model=get_pool()
        chat_model=model.chat
        embedding_model=model.embedding
        # 原文自己也要进向量库，检索时才能按语义把整段原始输入捞回来

        self.episodic_memory_repository.add_memory(
           origin_content,
           {
               "embedding":np.asarray(origin_embedding).astype(np.float32).tobytes(),
               "embedding_model":embedding_model.model_name,
           },
        )
        origin_content_id=origin_content.id
        memories_list=await asyncio.to_thread(modelService.to_memory,origin_content=origin_content.content, model=chat_model, additional_kwargs=kwargs)
        for memory in memories_list:
            embedding=await asyncio.to_thread(modelService.embedding,memory["content"],embedding_model)
            memory["embedding"]=np.asarray(embedding).astype(np.float32).tobytes()
            memory["embedding_model"]=embedding_model.model_name
        memories_list=await _process_similarity(memories_list)  #处理相似内容
        self.episodic_memory_repository.add_memory(memories_list,agent_id=store_request.agent_id,origin_content_id=origin_content_id)




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
