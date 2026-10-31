from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from  minimemo.config.data import settings

engine = create_engine(settings.DB_PATH, connect_args={"check_same_thread": False, "timeout": 30})
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
