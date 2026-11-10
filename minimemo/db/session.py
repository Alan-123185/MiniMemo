from sqlalchemy import NullPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from  minimemo.config.data import settings

engine = create_engine(settings.DB_DSN, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """
    FastAPI 依赖，每个请求一个 session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_session() -> Session:
    """
    直接拿一个 session，给脚本和测试用
    get_session 是生成器，直接调用拿到的是生成器而不是 session
    """
    return SessionLocal()



# 分布式锁专用：锁连接在整个抽取期间被独占持有（秒到分钟级），
# 走主池会直接把 pool_size + max_overflow 吃光。
# NullPool 不缓存连接，取到就是一条新物理连接，close 即断开，
# 断开必然回滚，行锁随之释放——正好是锁需要的语义。
lock_engine = create_engine(settings.DB_DSN, poolclass=NullPool)
LockSessionLocal = sessionmaker(bind=lock_engine, expire_on_commit=False)


def create_lock_session() -> Session:
    """
    给分布式锁用的 session，和主池完全隔离
    """
    return LockSessionLocal()
