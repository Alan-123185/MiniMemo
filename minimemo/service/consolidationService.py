import asyncio
from math import e
from typing import Literal
from loguru import logger
import numpy as np
from minimemo.common.existFact import existFact
from minimemo.common.memoryInfo import episodicMemoryInfo
from minimemo.common.requestSchema.storeRequest import episodeStoreRequest, originContentStoreRequest, storeRequest
from minimemo.config.data import settings
from minimemo.config.modelConfig import get_pool
from minimemo.db.session import create_session
from minimemo.models.origin_content import originContent
from minimemo.repository.embeddingRepository import embeddingRepository
from minimemo.repository.episodicMemoryRepository import episodicMemoryRepository
from minimemo.repository.originContentRepository import originContentRepository
from minimemo.service.modelService import modelService
from minimemo.tools.numpyTool import cosine_similarity



class consolidationService:
    """
    状态标记
    """
    episodic_memory_L1_lock=asyncio.Lock()

    """
    治理添加情景记忆的策略

    10.29 
    - 条数水位：同一 agent 攒够 N 条未抽取原文（N 取 6~12，看你的对话密度）
    - 时间水位：距最后一条原文超过 T 分钟（10~30 分钟），说明这段对话告一段落
    - 显式水位：调用方主动说「这里结束了一段」
    - 上限保护：未抽取原文攒到 M 条（比如 50）强制抽一次，兜住长期不触发的极端情况
    """
    @classmethod
    async def add_episodic_memory(cls, store_request: episodeStoreRequest):
        """
        10.29
        暂时先写个函数
        这个方法用于按批处理添加情景记忆 
        TODO: 需要制定添加情景记忆和语义记忆的策略和时机
        """

       
    @classmethod
    async def before_add_episodic_memory_L1(cls,store_request: originContentStoreRequest):
        """
        10.29
        第一层判断 只看某次添加原始内容之后积攒的未处理条数
        这个函数是用来判断需不需要进行情景记忆抽取，如果需要，返回待抽取的原文列表
        """
        #钩子链不走请求级依赖，session 自开自关
        session = create_session()
        try:
            pan = originContentRepository(session).get_not_archived_content(agent_id=store_request.agent_id)
        finally:
            session.close()
        #按会话拆分，每个会话各自攒各自的水位
        session_groups:dict[str,list[originContent]]={}
        for content in pan:
            session_groups.setdefault(content.session, []).append(content)
        #哪个会话攒够了阈值，就把那个会话的原文拿去抽取
        for session_id,group in session_groups.items():
            if len(group) >= settings.MAX_UNARCHIVED:
                yield group




    @classmethod
    async def add_episodic_memory_L1(cls, memory_list: list[originContent],store_request: originContentStoreRequest):
        """
        10.29
        第一层抽取情景记忆的逻辑  处理相似性 这个是分session处理的
        积累量超过阈值
        """

        async def _process_origin_content(memory_list: list[originContent]) -> tuple[str, dict[str, str]]:
            """
            10.29
            处理单条原文组装成输入
            给每条原文标上编号，同时留下编号到真实id的映射，
            落库时用它把 LLM 报回来的编号换回 origin_content_id
            """
            ret=[]
            id_map={}
            for index,memory in enumerate(memory_list):
                id_map[str(index)]=memory.id
                ret.append(f"[{index}] {memory.role}:{memory.content}")
            return "\n".join(ret), id_map

                


        model=get_pool()
        chat_model=model.chat
        embedding_model=model.embedding
        #gather 的每个任务各开一个 session，互不共享，事务边界各自独立
        session = create_session()
        try:
            origin_repo = originContentRepository(session)
            episodic_repo = episodicMemoryRepository(session)
            embedding_repo = embeddingRepository(session)
            need_process_content,id_map=await _process_origin_content(memory_list)
            #关键调用 ；制作情景记忆   已解决：怎么才能存储orign_content_id 关联到情景记忆上呢？  10.30
            memories_list=await asyncio.to_thread(modelService.to_episodic_memory,origin_content=need_process_content, model=chat_model)

            for memory in memories_list:
                embedding=await asyncio.to_thread(modelService.embedding,memory["content"],embedding_model)
                memory["embedding"]=np.asarray(embedding).astype(np.float32).tobytes()
                memory["embedding_model"]=embedding_model.model_name
            memory_info_list=[episodicMemoryInfo(content=memory["content"],
                                         origin_content_id=memory.get("origin_content_id"),
                                         embedding=memory["embedding"],
                                         embedding_model=memory["embedding_model"])
                                         for memory in memories_list]
            memories_list=await cls._process_similarity(memory_info_list,store_request,embedding_repo,episodic_repo)  #处理相似内容
            origin_repo.mark_archived([memory.id for memory in memory_list]) #标记已经存档
            episodic_repo.add_memory(memories_list,agent_id=store_request.agent_id,origin_content_ids=id_map)
        finally:
            session.close()




        

        


    @classmethod
    async def episodic_memory_L1(cls, store_request: originContentStoreRequest):
        """
        10.29
        第一层抽取情景记忆的逻辑
        积累量超过阈值
        """
        """
        单飞
        """
        async with cls.episodic_memory_L1_lock:
            group=[g async for session_id , g in  cls.before_add_episodic_memory_L1(store_request)]
            await asyncio.gather(*[cls.add_episodic_memory_L1(g,store_request) for g in group])
        
      
        
    @staticmethod
    async def _process_similarity(memories:list[episodicMemoryInfo],store_request:storeRequest,embedding_repo:embeddingRepository,episodic_repo:episodicMemoryRepository) -> list[episodicMemoryInfo]:
        """
        10.30 episodeMemory的三层去重策略
        碰库的 repo 从参数传进来：gather 的任务各用各的 session，
        不能挂 self 上（self 是所有任务共享的）
        """
        # 用 id 记录待丢弃的记忆，dict 不可哈希不能直接放进 set
        list_should_remove:set[int] = set()
        for index,memo in enumerate(memories):
            need_to_judge = []
            vector_list=embedding_repo.query_vectors(
                agent_id=store_request.agent_id,
                embedding_model=memo.embedding_model,
                query=np.frombuffer(memo.embedding, dtype=np.float32).tolist(),
                memory_type="episodic",  # 只和已有的情景记忆比，避免被同源原文误杀
                )
            for vector in vector_list:
                similarity = cosine_similarity(vector.embedding, memo.embedding)
                if similarity>=settings.SIM_TO_THROW:
                    # 如果相似度超过阈值，则从记忆列表中移除该记忆
                    list_should_remove.add(index)
                    break
                elif settings.SIMILARITY_THRESHOLD <= similarity < settings.SIM_TO_THROW:
                    # 如果相似度在阈值范围内，交给大模型判断
                    need_to_judge.append(vector)
            if need_to_judge:
                memo_list=episodic_repo.search_memory([need.memory_id for need in need_to_judge])
                pan_dict= modelService.judge_similarity(fact1=memo.content,fact2=[existFact(content=m.content, memory_id=m.id) for m in memo_list], model=get_pool().chat)
                #评测逻辑
                if pan_dict["action"] == "ADD":
                    pass
                elif pan_dict["action"] == "UPDATE":
                    target=pan_dict["target_id"]
                    episodic_repo.update_memory(memory_id=target, content=memo.content, new_embedding=memo.embedding)
                    list_should_remove.add(index)
                elif pan_dict["action"] == "DELETE":
                    target=pan_dict["target_id"]
                    episodic_repo.kill_memory(memory_id=target)
                elif pan_dict["action"] == "NONE":
                    list_should_remove.add(index)

        return [m for idx, m in enumerate(memories) if idx not in list_should_remove]