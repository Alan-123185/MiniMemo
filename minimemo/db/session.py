from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from  minimemo.config.data import settings

engine = create_async_engine(settings.DB_DSN, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session():
    """
    FastAPI 依赖，每个请求一个 session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()


def create_session() -> AsyncSession:
    """
    直接拿一个 session，给脚本和测试用
    get_session 是生成器，直接调用拿到的是生成器而不是 session
    """
    return SessionLocal()
