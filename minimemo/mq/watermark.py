from loguru import logger

from minimemo.service.consolidationService import consolidationService


"""
水位判断

情景抽取的触发条件是「某个会话够水位了」，而不是「来了一条原文」，
所以消息只是「去看一眼」的信号，判断还是走抽取服务里原有的那两条水位线。

consumer 与兜底扫描器共用这一份，保证两条路径的判断口径完全一致。
"""


async def get_ready_sessions(agent_id: str) -> set[str]:
    """
    返回该 agent 下所有已达水位的会话 id：够条数或够时间的都算  注：这是两个水位判断函数唯一被调用到的地方
    """
    session_stats = await consolidationService.get_unarchive_session_by_agent(agent_id)
    ready = {sid async for sid in consolidationService.before_add_episodic_memory_L1(session_stats)}
    ready |= {sid async for sid in consolidationService.before_add_episodic_memory_L2(session_stats)}
    return ready
