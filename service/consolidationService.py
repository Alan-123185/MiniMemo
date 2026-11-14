import asyncio
import datetime
from loguru import logger
from common.existFact import existFact
from common.memoryInfo import episodicMemoryInfo, memoryInfo, semanticMemoryInfo
from common.unarchiveSessionStatus import unarchiveAgentStatus, unarchiveSessionStatus
from config.data import settings
from config.modelConfig import modelConfig, modelPool
from db.session import create_session
from models.memoryModel.episodicMemory import episodicMemory
from models.memoryModel.origin_content import originContent
from repository.embeddingRepository import embeddingRepository
from repository.episodicMemoryRepository import episodicMemoryRepository
from repository.memoryRepository import memoryRepository
from repository.originContentRepository import originContentRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from repository.userRepository import userRepository
from service.modelService import modelService
from tools.backgroundTask import spawn
from tools.numpyTool import cosine_similarity
from tools.sessionLock import try_agent_lock, try_session_lock




class consolidationService:

    """
    治理添加情景记忆的策略

    10.29
    - 条数水位：同一 agent 攒够 N 条未抽取原文（N 取 6~12，看你的对话密度）
    - 时间水位：距最后一条原文超过 T 分钟（10~30 分钟），说明这段对话告一段落
    - 显式水位：调用方主动说「这里结束了一段」
    - 上限保护：未抽取原文攒到 M 条（比如 50）强制抽一次，兜住长期不触发的极端情况
    """


    @staticmethod
    async def sort_prompt_for_add_episodics(memory_list: list[originContent]) -> tuple[str, dict[str, str]]:
        """
        特殊内部方法 专门用于主动触发情景记忆的情况下原始prompt的组织
        """
        ret=[]
        id_map={}
        for index,memory in enumerate(memory_list):
            id_map[str(index)]=memory.id
            ret.append(f"[{index}] {memory.role}:{memory.content}")
        return "\n".join(ret), id_map





    @staticmethod
    async def sort_prompt_for_add_semantics(memory_list: list[episodicMemory]) -> str:
        """
        特殊内部方法 专门用于主动触发语义记忆的情况下原始prompt的组织
        """
        ret=[]
        for index,memory in enumerate(memory_list):
            ret.append(f"[{index}] {memory.content}")
        return "\n".join(ret)


    @classmethod
    async def get_unarchive_session_by_agent(cls,agent_id:str) -> list[unarchiveSessionStatus]:
        """
        注：意义不明
        这个函数把一个agent下的所有会话的未归档原文统计状态拿出来 以session为单位 扫origin_content表
        """
        session=create_session()
        try:
            origin_repo=originContentRepository(session)
            session_stats=await origin_repo.get_unarchived_session_stats(agent_id)
        finally:
            await session.close()
        return session_stats



    @classmethod
    async def get_unarchive_agent(cls) -> list[unarchiveAgentStatus]:
        """
        注：意义不明
        这个函数把未归档的agent状态获取出来 扫episodic_memory表
        """
        session=create_session()
        try:
            episodic_repo=episodicMemoryRepository(session)
            agent_stats=await episodic_repo.get_unarchived_agent_stats()
        finally:
            await session.close()
        return agent_stats



    @classmethod
    async def consolidate_semantics(cls,agent_id:str):
        """
        11.2
        语义提炼的唯一入口：把上次提炼之后新增的情景记忆提炼成语义记忆
        循环与主动调用都走这里
        互斥粒度是 agent：语义事实本来就是跨会话的
        11.12
        语义记忆上agent表行锁
        """
        async with try_agent_lock(agent_id) as lock_session:
            if lock_session is None:
                return
            try:
                input=await cls.before_add_semantic_memory(agent_id)
                await cls.add_semantic_memory(input,agent_id) # type: ignore
            except Exception as e:
                await lock_session.rollback()   # 释放锁，数据不落
                logger.exception(f"语义记忆提取失败，本轮放弃-------- {e}")
                raise




    @classmethod
    async def consolidate_episodics(cls,agent_id:str,session_id:str):
        """
        11.1
        这个函数目前只被消费者队列调用 轮询循环调用的是消费者队列里的消费方法
        11.10
        先给添加情景记忆的函数加个行锁，别的后面再考虑
        """
        async with try_session_lock(agent_id, session_id) as lock_session:
            if lock_session is None:
                # 别人在抽，或会话不存在 —— 正常跳过，等下轮
                return
            # ---- 到这里说明锁已经在我手里 ----
            try:
                input=await cls.before_add_episodic_memory(agent_id,session_id)
                await cls.add_episodic_memory(agent_id,input) # type: ignore
            except Exception as e:
                await lock_session.rollback()   # 释放锁，数据不落
                logger.exception(f"情景记忆提取失败，本轮放弃-------- {e}")
                raise



    """
    两个关于情景记忆的水位判断函数

    10.29
    第一层判断 只看某次添加原始内容之后积攒的未处理条数
    这个函数是用来判断需不需要进行情景记忆抽取，如果需要，返回待抽取的会话id
    """
    @classmethod
    async def before_add_memory_L1(cls,stats:list[unarchiveSessionStatus] | list[unarchiveAgentStatus],mode=settings.getMemoryMode):

        #哪个会话攒够了阈值，就把那个会话的原文拿去抽取
        for s in stats:
            if mode == "episodic" and s.count >= settings.MAX_UNARCHIVED_EPISODIC:
                yield s.session # type: ignore
            elif mode == "semantic" and s.count >= settings.MAX_UNARCHIVED_SEMANTIC:
                yield s.agent # type: ignore

    """
    10.31
    第二层：时间水位
    """
    @classmethod
    async def before_add_memory_L2(cls,stats:list[unarchiveSessionStatus] | list[unarchiveAgentStatus],mode=settings.getMemoryMode):
        """
        10.31
        第二层判断 看时间
        这个函数是用来判断需不需要进行情景记忆抽取，如果需要，返回待抽取的会话id
        """
        #哪个会话攒够了阈值，就把那个会话的原文拿去抽取
        for s in stats:
            #距离最新一条原文的落库时间超过 T 秒就说明这段对话凉了
            if mode == "episodic" and datetime.datetime.now() - s.the_latest_create_time >= datetime.timedelta(seconds=settings.MAX_UNARCHIVED_TIME_EPISODIC):
                yield s.session # type: ignore
            elif mode == "semantic" and datetime.datetime.now() - s.the_latest_create_time >= datetime.timedelta(seconds=settings.MAX_UNARCHIVED_TIME_SEMANTIC):
                yield s.agent # type: ignore


    """
    关于情景记忆抽取的函数 拆分 11.11
    """
    @classmethod
    async def before_add_episodic_memory(cls,agent_id:str,session_id:str) ->  tuple[list[episodicMemoryInfo], list[tuple[episodicMemoryInfo, dict]], list[originContent], dict] | None:
        """
        111
        这个函数用于处理session的情景记忆提炼 不做任何数据库操作
        """
        #计算待抽取的初始记忆列表

        session = create_session()
        try:
            config = await userRepository(session).get_models_by_agent(agent_id)
            origin_repo = originContentRepository(session)
            origin_content_list=await origin_repo.fetch_unarchived_by_session(agent_id, session_id)
        finally:
            await session.close()
        if not origin_content_list:
            logger.info(f"session_id={session_id} 没有未归档原文，跳过情景记忆抽取")
            return


        #调用模型先把这东西抽成情景记忆    长耗时
        model = modelPool(**config.model_dump(exclude_none=True))
        chat_model = model.chat
        embedding_model = model.embedding
        try:
            need_process_content,id_map=await cls.sort_prompt_for_add_episodics(origin_content_list)
            episodic_memory_list,truncate_from=await modelService.to_episodic_memory(
                origin_content=need_process_content,
                model=chat_model,
            )
            archived_list=origin_content_list if truncate_from<=0 else origin_content_list[:truncate_from]


            #处理相似记忆               长耗时
            for memory in episodic_memory_list:
                embedding=await modelService.embedding(memory["content"], embedding_model)
                memory["embedding"]=embedding
                memory["embedding_model"]=embedding_model.model_name
            memory_info_list=[episodicMemoryInfo(content=memory["content"],
                                            origin_content_id=memory.get("origin_content_id"),
                                            embedding=memory["embedding"],
                                            embedding_model=memory["embedding_model"])
                                            for memory in episodic_memory_list]
            episodic_memory_list, similarity_decisions = await cls._process_similarity(
                memory_info_list, agent_id, "episodic", chat_model=chat_model
            )
            return episodic_memory_list, similarity_decisions, archived_list,id_map
        except Exception as e:
            logger.exception(f"情景记忆抽取失败:{e}")
            raise


    """
    两个关于语义记忆和情景记忆的添加主函数
    """
    @classmethod
    async def add_episodic_memory(cls,agent_id:str,episodic_memory_input:tuple[list[episodicMemoryInfo], list[tuple[memoryInfo, dict]], list[originContent], dict] | None):
        """
        10.29
        抽取情景记忆的逻辑
        11.11 集中处理数据库操作 原子事务
        积累量超过阈值
        """
        if not episodic_memory_input:
            logger.info(f"没有新的情景记忆，跳过落库")
            return
        episodic_memory_list, similarity_decisions, archived_list,id_map= episodic_memory_input
        session = create_session()
        try:
            origin_repo = originContentRepository(session)
            episodic_repo = episodicMemoryRepository(session)
            await cls._apply_similarity_decisions(
                episodic_repo, similarity_decisions, agent_id=agent_id
            )
            await origin_repo.mark_archived([memory.id for memory in archived_list], agent_id=agent_id)
            await episodic_repo.add_memory(
                episodic_memory_list,
                agent_id=agent_id,
                origin_content_ids=id_map,
                commit=False,
            )
            await session.commit()
        finally:
            await session.close()


    @classmethod
    async def before_add_semantic_memory(cls,agent_id:str) -> tuple[list[semanticMemoryInfo], list[tuple[memoryInfo, dict]], list[episodicMemory]] | None:
        """
        11.2
        这个函数用于预处理agent的语义记忆提炼 不做任何数据库操作
        """
        session = create_session()
        try:
            config = await userRepository(session).get_models_by_agent(agent_id)
            #先把需要提炼的情景记忆抽出来
            episodic_repo = episodicMemoryRepository(session)
            episodic_memories_list=await episodic_repo.fetch_unarchived_by_agent(agent_id)
        finally:
            await session.close()
        if not episodic_memories_list:
            logger.info(f"agent_id={agent_id} 没有未归档情景记忆，跳过语义记忆提炼")
            return


        #调用模型先把这东西抽成语义记忆    长耗时
        model = modelPool(**config.model_dump(exclude_none=True))
        chat_model = model.chat
        embedding_model = model.embedding
        try:
            need_process_content=await cls.sort_prompt_for_add_semantics(episodic_memories_list)
            semantic_memory_list=await modelService.to_semantic_memory(
                episodic_memories=need_process_content,
                model=chat_model,
            )
            archived_list=episodic_memories_list


            #处理相似记忆               长耗时
            for memory in semantic_memory_list:
                embedding=await modelService.embedding(memory["content"], embedding_model)
                memory["embedding"]=embedding
                memory["embedding_model"]=embedding_model.model_name
            memory_info_list=[semanticMemoryInfo(content=memory["content"],
                                            type=memory.get("type","fact"),
                                            is_alive=memory.get("is_alive",True),
                                            embedding=memory["embedding"],
                                            embedding_model=memory["embedding_model"])
                                            for memory in semantic_memory_list]
            semantic_memory_list, similarity_decisions = await cls._process_similarity(
                memory_info_list, agent_id, "semantic", chat_model=chat_model
            )
            return semantic_memory_list, similarity_decisions, archived_list  # type: ignore
        except Exception as e:
            logger.exception(f"语义记忆抽取失败:{e}")
            raise


    @classmethod
    async def add_semantic_memory(cls, semantic_memory_input: tuple[list[semanticMemoryInfo], list[tuple[memoryInfo, dict]], list[episodicMemory]] | None, agent_id: str):
        """
        11.2
        把一批情景记忆提炼成语义记忆
        失败整批不推进水位线，下轮重来
        """
        if not semantic_memory_input:
            logger.info(f"没有新的语义记忆，跳过落库")
            return
        semantic_memory_list, similarity_decisions, archived_list = semantic_memory_input
        session = create_session()
        try:
            episodic_repo = episodicMemoryRepository(session)
            semantic_repo = semanticMemoryRepository(session)
            await cls._apply_similarity_decisions(
                semantic_repo, similarity_decisions, agent_id=agent_id
            )
            await episodic_repo.mark_archived([memory.id for memory in archived_list], agent_id=agent_id)
            await semantic_repo.add_memory(semantic_memory_list,agent_id=agent_id,commit=False)
            await session.commit()
            #语义记忆落库成功了才推进水位线，失败的话下轮整批重来
        finally:
            await session.close()



    """
    注：意义不明
    这个函数是用来应用相似性判断的结果的，更新或删除已有记忆
    """
    @staticmethod
    async def _apply_similarity_decisions(
        repository: memoryRepository,
        decisions: list[tuple[memoryInfo, dict]],
        *, agent_id: str,
    ) -> None:
        for memory, decision in decisions:
            if decision["action"] == "UPDATE":
                await repository.update_memory(
                    memory_id=decision["target_id"],
                    content=memory.content,
                    new_embedding=memory.embedding,
                    agent_id=agent_id,
                )
            elif decision["action"] == "DELETE":
                await repository.kill_memory(memory_id=decision["target_id"], agent_id=agent_id)



    """
    11.10
    
    先不管这个函数
    这个函数只能暂时这么写   只知道它的功能就是处理相似的记忆
    相似记忆搜索策略有大问题
    数据库事务的范围和原子性一塌糊涂
    11.11
    稍微处理了一下 增加了并发能力 暂时先这样
    """
    
    @staticmethod
    async def _process_similarity[T: memoryInfo](
        memories: list[T], agent_id: str, memory_type: str, *, chat_model: modelConfig
    ) -> tuple[list[T], list[tuple[T, dict]]]:

        async def _process_one_memory(
            index: int,
            memo:memoryInfo,
            agent_id: str,
            memory_type: str,
            sem: asyncio.Semaphore,
        ) -> tuple[int, str, dict | None]:
            """处理单条记忆，返回 (index, action, pan_dict)

            action:
                "THROW"  -> 向量相似度超高，直接丢弃
                "KEEP"   -> 无候选，保留，不调模型
                "JUDGED" -> 调了模型，pan_dict 是模型决策
            """
            async with sem:                              # 控制并发，别打爆连接池和 LLM RPM
                session = create_session()
                try:
                    embedding_repo = embeddingRepository(session)
                    existing_repo = (
                        semanticMemoryRepository(session)
                        if memory_type == "semantic"
                        else episodicMemoryRepository(session)
                    )

                    vector_list = await embedding_repo.query_vectors(
                        agent_id=agent_id,
                        embedding_model=memo.embedding_model,
                        query=memo.embedding,
                        memory_type=memory_type,
                    )

                    need_to_judge = []
                    for vector, similarity in vector_list:
                        if similarity >= settings.SIM_TO_THROW:
                            return (index, "THROW", None)          # 早退，session 由 finally 关
                        elif settings.SIMILARITY_THRESHOLD <= similarity < settings.SIM_TO_THROW:
                            need_to_judge.append(vector)

                    if not need_to_judge:
                        return (index, "KEEP", None)
                    
                    memo_list = await existing_repo.search_memory(
                        [need.memory_id for need in need_to_judge]
                    )
                    candidates = [existFact(content=m.content, memory_id=m.id) for m in memo_list]
                    if not candidates:
                        return (index, "KEEP", None) 
                    
                finally:
                    await session.close()                    # 连接已归还，模型等待不占连接
                    
                # session 关闭后调模型
                pan_dict = await modelService.judge_similarity(
                    fact1=memo.content,
                    fact2=candidates,
                    model=chat_model,
                )
                return (index, "JUDGED", pan_dict)

        if not memories:
            return ([], [])

        sem = asyncio.Semaphore(settings.MAX_SIM_CONCURRENCY)   # 例如 5
        results = await asyncio.gather(*[
            _process_one_memory(i, m, agent_id, memory_type, sem)
            for i, m in enumerate(memories)
        ])

        list_should_remove: set[int] = set()
        decisions: list[tuple[T, dict]] = []

        for index, action, pan_dict in results:
            if action == "THROW":
                list_should_remove.add(index)
            elif action == "JUDGED":
                decisions.append((memories[index], pan_dict))       # type: ignore # 所有过模型的都进 decisions
                if pan_dict["action"] in {"UPDATE", "NONE"}:        # type: ignore
                    list_should_remove.add(index)
            # action == "KEEP"：不动

        return (
            [m for i, m in enumerate(memories) if i not in list_should_remove],
            decisions,
        )




