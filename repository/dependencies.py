from fastapi.params import Depends
from starlette.middleware.sessions import Session
from db.session import get_session
from repository.agentRepository import agentRepository
from repository.memoryRepository import memoryRepository
from repository.originContentRepository import originContentRepository



def get_agent_repo(session:Session=Depends(get_session)):
    return agentRepository(session)

def get_memory_repo(session:Session=Depends(get_session)):
    return memoryRepository(session)

def get_origin_content_repo(session:Session=Depends(get_session)):
    return originContentRepository(session)