from fastapi.params import Depends
from starlette.middleware.sessions import Session
from  minimemo.db.session import get_session
from  minimemo.repository.agentRepository import agentRepository
from  minimemo.repository.memoryRepository import memoryRepository
from  minimemo.repository.originContentRepository import originContentRepository
from  minimemo.repository.embeddingRepository import embeddingRepository


def get_agent_repo(session:Session|None=None):
    if session is None:
        session=get_session()
    return agentRepository(session)

def get_memory_repo(session:Session|None=None):
    if session is None:
        session=get_session()
    return memoryRepository(session)

def get_origin_content_repo(session:Session|None=None):
    if session is None:
        session=get_session()
    return originContentRepository(session)

def get_embedding_repo(session:Session|None=None):
    if session is None:
        session=get_session()
    return embeddingRepository(session)