from contextlib import asynccontextmanager
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from minimemo.config.data import settings


"""
会话级分布式锁

11.10
锁的载体是 sessions 表里 (agent_id, session_id) 那一行的行锁，
用 FOR UPDATE SKIP LOCKED 非阻塞地取，拿不到就直接跳过，不进队排队。

三条必须守住的规则：

1. 走独立连接池，不占主池。锁连接在整个抽取期间被独占持有，
   走主池会把 pool_size + max_overflow 吃光。

2. 用 NullPool 不用 QueuePool。释放锁靠 close() 断开连接 → 事务回滚 → 行锁释放。
   池化连接 close() 只是归还，事务仍然开着，锁还在自己手里。

3. 锁事务必须从取锁一直开到情景记忆落库 commit。中途 commit 或 close
   都会当场放掉行锁，抽取全程就裸奔了。所以这里 yield 的是 session，
   调用方要接着拿它读原文、写情景记忆，最后一起提交。
"""

# 分布式锁专用：锁连接在整个抽取期间被独占持有（秒到分钟级），
# 走主池会直接把 pool_size + max_overflow 吃光。
# NullPool 不缓存连接，取到就是一条新物理连接，close 即断开，
# 断开必然回滚，行锁随之释放——正好是锁需要的语义。
lock_engine = create_async_engine(settings.DB_DSN, poolclass=NullPool)
LockSessionLocal = async_sessionmaker(bind=lock_engine, expire_on_commit=False)


def create_lock_session() -> AsyncSession:
    """
    给分布式锁用的 session，和主池完全隔离
    """
    return LockSessionLocal()

@asynccontextmanager
async def try_session_lock(agent_id: str, session_id: str):
    """
    拿到该会话的行锁就用这个 session 干完整轮抽取，拿不到就 yield None

    拿到 None 表示该会话正被别人抽取（或该会话没在 sessions 表里），
    调用方直接返回即可，等下轮触发再来。
    """
    session = create_lock_session()
    try:
        row = (await session.execute(
            text(
                "SELECT id FROM sessions "
                "WHERE agent_id = :agent_id AND session_id = :session_id "
                "FOR UPDATE SKIP LOCKED"
            ),
            {"agent_id": agent_id, "session_id": session_id},
        )).first()
        if row is None:
            logger.info(f"会话已被占用或无注册记录，本次跳过 agent_id={agent_id} session_id={session_id}")
        yield session if row is not None else None
    finally:
        # 这里必须在抽取结束之后执行，它同时负责释放行锁
        await session.close()
