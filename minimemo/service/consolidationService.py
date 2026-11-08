import asyncio
import datetime
from math import e
from loguru import logger
import numpy as np
from minimemo.common.existFact import existFact
from minimemo.common.memoryInfo import episodicMemoryInfo, memoryInfo, semanticMemoryInfo
from minimemo.common.unarchiveSessionStatus import unarchiveSessionStatus
from minimemo.config.data import settings
from minimemo.config.modelConfig import get_pool
from minimemo.db.session import create_session
from minimemo.models.memoryModel.episodicMemory import episodicMemory
from minimemo.models.origin_content import originContent
from minimemo.repository.embeddingRepository import embeddingRepository
from minimemo.repository.episodicMemoryRepository import episodicMemoryRepository
from minimemo.repository.memoryRepository import memoryRepository
from minimemo.repository.originContentRepository import originContentRepository
from minimemo.repository.semanticMemoryRepository import semanticMemoryRepository
from minimemo.service.modelService import modelService
from minimemo.tools.backgroundTask import spawn
from minimemo.tools.numpyTool import cosine_similarity



class consolidationService:
    """
    状态标记
    """
    _loop_tasks: dict[str, asyncio.Task] = {}

    # 抽取的互斥粒度是会话：同一 agent 下不同会话可以并发抽
    _session_locks: dict[tuple[str, str], asyncio.Lock] = {}

    # 语义提炼的互斥粒度是 agent：提炼跨会话的事实
    _semantic_locks: dict[str, asyncio.Lock] = {}

    # 语义提炼的进度：agent_id -> 上次提炼到的情景记忆时间
    # 只存内存，宿主重启丢了顶多把同一批情景记忆再提炼一遍，三层去重兜住
    _episodic_watermark: dict[str, datetime.datetime] = {}

    """
    治理添加情景记忆的策略

    10.29 
    - 条数水位：同一 agent 攒够 N 条未抽取原文（N 取 6~12，看你的对话密度）
    - 时间水位：距最后一条原文超过 T 分钟（10~30 分钟），说明这段对话告一段落
    - 显式水位：调用方主动说「这里结束了一段」
    - 上限保护：未抽取原文攒到 M 条（比如 50）强制抽一次，兜住长期不触发的极端情况
    """



    @staticmethod
    async def process_origin_content(memory_list: list[originContent]) -> tuple[str, dict[str, str]]:
        """
        特殊内部方法 专门用于主动触发情景记忆的情况下原始prompt的组织
        """
        ret=[]
        id_map={}
        for index,memory in enumerate(memory_list):
            id_map[str(index)]=memory.id
            ret.append(f"[{index}] {memory.role}:{memory.content}")
        return "\n".join(ret), id_map
    


    

    @classmethod
    async def before_add_episodic_memory(cls,agent_id:str) -> list[unarchiveSessionStatus]:
            session=create_session()
            try:
                origin_repo=originContentRepository(session)
                session_stats=origin_repo.get_unarchived_session_stats(agent_id)
            finally:
                session.close()
            return session_stats

    
    @classmethod
    async def before_add_episodic_memory_L1(cls,session_stats:list[unarchiveSessionStatus]):
        """
        10.29
        第一层判断 只看某次添加原始内容之后积攒的未处理条数
        这个函数是用来判断需不需要进行情景记忆抽取，如果需要，返回待抽取的会话id
        """
        #哪个会话攒够了阈值，就把那个会话的原文拿去抽取
        for session in session_stats:
            if session.count >= settings.MAX_UNARCHIVED:
                yield session.session


    """
    10.31
    开始做第二层：时间水位
    """
    @classmethod
    async def before_add_episodic_memory_L2(cls,session_stats:list[unarchiveSessionStatus]):
        """
        10.31
        第二层判断 看时间
        这个函数是用来判断需不需要进行情景记忆抽取，如果需要，返回待抽取的会话id
        """
        #哪个会话攒够了阈值，就把那个会话的原文拿去抽取
        for session in session_stats:
            #距离最新一条原文的落库时间超过 T 秒就说明这段对话凉了
            if datetime.datetime.now() - session.the_latest_create_time >= datetime.timedelta(seconds=settings.MAX_UNARCHIVED_TIME):
                yield session.session


    @classmethod
    async def add_episodic_memory(cls, memory_list: list[originContent],agent_id: str):
        """
        10.29
        抽取情景记忆的逻辑  处理相似性 这个是分session处理的
        积累量超过阈值
        """
        model=get_pool()
        chat_model=model.chat
        embedding_model=model.embedding
        #gather 的每个任务各开一个 session，互不共享，事务边界各自独立
        session = create_session()
        try:
            origin_repo = originContentRepository(session)
            episodic_repo = episodicMemoryRepository(session)
            embedding_repo = embeddingRepository(session)
            need_process_content,id_map=await cls.process_origin_content(memory_list)
            #关键调用 ；制作情景记忆   已解决：怎么才能存储orign_content_id 关联到情景记忆上呢？  10.30
            memories_list,truncate_from=await asyncio.to_thread(modelService.to_episodic_memory,origin_content=need_process_content, model=chat_model)

            #结尾把一件事讲到一半时，只归档截断点之前的原文，截断点及之后的滚入下一轮抽取
            archived_list=memory_list if truncate_from<=0 else memory_list[:truncate_from]
            for memory in memories_list:
                embedding=await asyncio.to_thread(modelService.embedding,memory["content"],embedding_model)
                memory["embedding"]=embedding
                memory["embedding_model"]=embedding_model.model_name
            memory_info_list=[episodicMemoryInfo(content=memory["content"],
                                         origin_content_id=memory.get("origin_content_id"),
                                         embedding=memory["embedding"],
                                         embedding_model=memory["embedding_model"])
                                         for memory in memories_list]
            memories_list=await cls._process_similarity(memory_info_list,agent_id,embedding_repo,episodic_repo,"episodic")  #处理相似内容
            origin_repo.mark_archived([memory.id for memory in archived_list]) #标记已经存档，截断点之后的留给下一轮
            episodic_repo.add_memory(memories_list,agent_id=agent_id,origin_content_ids=id_map)
        finally:
            session.close()




    @classmethod
    async def episodic_memory_consolidation(cls,agent_id:str,session_id:str):
        """
        11.1
        给调用方主动调用接口
        主动触发情景记忆抽取
          调用方自己选定session_id和agent_id
        """
        await cls.consolidate_episodics(agent_id, session_id)


    @classmethod
    async def semantic_memory_consolidation(cls,agent_id:str):
        """
        11.2
        给调用方主动调用接口
        主动触发语义记忆提炼，调用方自己选定agent_id
        """
        await cls.consolidate_semantics(agent_id)


    @classmethod
    async def consolidate_semantics(cls,agent_id:str):
        """
        11.2
        语义提炼的唯一入口：把上次提炼之后新增的情景记忆提炼成语义记忆
        循环与主动调用都走这里
        互斥粒度是 agent：语义事实本来就是跨会话的
        """
        lock=cls._semantic_locks.setdefault(agent_id, asyncio.Lock())
        async with lock:
            session = create_session()
            try:
                episodic_repo = episodicMemoryRepository(session)
                watermark=cls._episodic_watermark.get(agent_id)
                source_list=episodic_repo.fetch_since(agent_id, watermark)
            finally:
                session.close()
            if not source_list:
                logger.info(f"agent_id={agent_id} 没有新的情景记忆，跳过语义记忆提炼")
                return
            await cls.add_semantic_memory(source_list,agent_id)


    @classmethod
    async def add_semantic_memory(cls, memory_list: list[episodicMemory],agent_id: str):
        """
        11.2
        把一批情景记忆提炼成语义记忆
        失败整批不推进水位线，下轮重来
        """
        model=get_pool()
        chat_model=model.chat
        embedding_model=model.embedding
        session = create_session()
        try:
            semantic_repo = semanticMemoryRepository(session)
            embedding_repo = embeddingRepository(session)
            need_process_content="\n".join(f"- {memory.content}" for memory in memory_list)
            memories_list=await asyncio.to_thread(modelService.to_semantic_memory,episodic_memories=need_process_content, model=chat_model)
            memory_info_list=[]
            for memory in memories_list:
                embedding=await asyncio.to_thread(modelService.embedding,memory["content"],embedding_model)
                memory_info_list.append(semanticMemoryInfo(
                    content=memory["content"],
                    type=memory.get("type","fact"),
                    is_alive=memory.get("is_alive",True),
                    embedding=embedding,
                    embedding_model=embedding_model.model_name))
            await cls._process_similarity(memory_info_list,agent_id,embedding_repo,semantic_repo,"semantic")
            semantic_repo.add_memory(memory_info_list,agent_id=agent_id)
            #语义记忆落库成功了才推进水位线，失败的话下轮整批重来
            cls._episodic_watermark[agent_id]=memory_list[-1].create_time
        finally:
            session.close()





    @classmethod
    async def consolidate_episodics(cls,agent_id:str,session_id:str):
        """
        11.1
        抽取的唯一入口：把一个会话的未归档原文抽成情景记忆
        循环与主动调用都走这里，区别只在谁来挑会话
        取数放在锁内，避免两条路径拿到同一批原文各抽一遍
        """
        lock=cls._session_locks.setdefault((agent_id, session_id), asyncio.Lock())
        async with lock:
            session = create_session()
            try:
                origin_repo = originContentRepository(session)
                origin_content_list=origin_repo.fetch_unarchived_by_session(agent_id, session_id)
            finally:
                session.close()
            if not origin_content_list:
                logger.info(f"session_id={session_id} 没有未归档原文，跳过情景记忆抽取")
                return
            await cls.add_episodic_memory(origin_content_list,agent_id)
        

        

   



    @classmethod
    def start_consolidation_loop(cls,agent_id:str):
        """
        10.29
        自动归档情景记忆的循环 
        注意：会遍历一个agent的所有会话
        交由宿主调用
        """
        async def episodic_memory_consolidation_loop(agent_id:str):
            """自动归档情景记忆的循环 交由宿主调用 """
            while True:
                try:
                    session_stats = await cls.before_add_episodic_memory(agent_id)
                    #两条水位线各扫一遍，拿到的会话号合起来抽
                    session_ids = [sid async for sid in cls.before_add_episodic_memory_L1(session_stats)]
                    session_ids += [sid async for sid in cls.before_add_episodic_memory_L2(session_stats)]
                    #同一会话可能同时够条数和超时，去重一下
                    await asyncio.gather(*[cls.consolidate_episodics(agent_id, sid) for sid in set(session_ids)])
                except Exception as e:
                    logger.error(f"情景记忆循环出错: {e}")
                await asyncio.sleep(settings.EPISODIC_CONSOLIDATION_INTERVAL)   #睡一段时间间隔
        if agent_id in cls._loop_tasks :
            logger.warning(f"情景记忆循环已经在运行，请勿重复启动，agent_id={agent_id}")
            return 
        cls._loop_tasks[agent_id] = spawn(episodic_memory_consolidation_loop(agent_id))
    


    @staticmethod
    async def _process_similarity[T:memoryInfo](memories:list[T],agent_id:str,embedding_repo:embeddingRepository,existing_repo:memoryRepository,memory_type:str) -> list[T]:
        """
        10.30 episodeMemory的三层去重策略
        碰库的 repo 从参数传进来：gather 的任务各用各的 session，
        不能挂 self 上（self 是所有任务共享的）
        情景和语义的提炼都走这里，参数决定和哪类已有记忆比
        """
        # 用 id 记录待丢弃的记忆，dict 不可哈希不能直接放进 set
        list_should_remove:set[int] = set()
        for index,memo in enumerate(memories):
            need_to_judge = []
            vector_list=embedding_repo.query_vectors(
                agent_id=agent_id,
                embedding_model=memo.embedding_model,
                query=memo.embedding,
                memory_type=memory_type,  # 只和同类型记忆比，避免被同源原文误杀
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
                memo_list=existing_repo.search_memory([need.memory_id for need in need_to_judge])
                pan_dict= modelService.judge_similarity(fact1=memo.content,fact2=[existFact(content=m.content, memory_id=m.id) for m in memo_list], model=get_pool().chat)
                #评测逻辑
                if pan_dict["action"] == "ADD":
                    pass
                elif pan_dict["action"] == "UPDATE":
                    target=pan_dict["target_id"]
                    existing_repo.update_memory(memory_id=target, content=memo.content, new_embedding=memo.embedding)
                    list_should_remove.add(index)
                elif pan_dict["action"] == "DELETE":
                    target=pan_dict["target_id"]
                    existing_repo.kill_memory(memory_id=target)
                elif pan_dict["action"] == "NONE":
                    list_should_remove.add(index)

        return [m for idx, m in enumerate(memories) if idx not in list_should_remove]





    

    



    
    