
from typing import Literal

from config.data import settings

from service.consolidationService import consolidationService


"""
水位判断

情景抽取的触发条件是「某个会话够水位了」，而不是「来了一条原文」，
所以消息只是「去看一眼」的信号，判断还是走抽取服务里原有的那两条水位线。

consumer 与兜底扫描器共用这一份，保证两条路径的判断口径完全一致。
"""




async def get_ready_memory(
    agent_id: str | None = None,
    mode: Literal["episodic", "semantic"] = settings.getMemoryMode,
) -> set[str]:
    """
    情景模式返回指定 agent 下已达水位的会话 id；语义模式返回 agent id。
    语义扫描不传 agent_id 时一次统计所有 agent，消费时传入则只判断该 agent。
    """
    if mode=="episodic":
        if agent_id is None:
            raise ValueError("情景记忆水位判断需要 agent_id")
        session_stats = await consolidationService.get_unarchive_session_by_agent(agent_id)
        ready = {sid async for sid in consolidationService.before_add_memory_L1(session_stats,mode="episodic")}
        ready |= {sid async for sid in consolidationService.before_add_memory_L2(session_stats,mode="episodic")}
    elif mode=="semantic":
        session_stats = await consolidationService.get_unarchive_agent()
        if agent_id is not None:
            session_stats = [s for s in session_stats if s.agent == agent_id]
        ready = {sid async for sid in consolidationService.before_add_memory_L1(session_stats,mode="semantic")}
        ready |= {sid async for sid in consolidationService.before_add_memory_L2(session_stats,mode="semantic")}
    else:
        raise ValueError(f"不支持的记忆类型: {mode}")
    return ready


