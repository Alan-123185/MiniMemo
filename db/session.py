from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_session() :
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()