from fastapi.params import Depends
from starlette.middleware.sessions import Session

from db.session import get_session
from repository.agentRepository import agentRepository


def get_agent_repo(session:Session=Depends(get_session)):
    return agentRepository(session)