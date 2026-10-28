from fastapi import Depends
from sqlalchemy.orm import Session

from  minimemo.db.session import get_session
from  minimemo.repository.agentRepository import agentRepository
from  minimemo.repository.embeddingRepository import embeddingRepository
from  minimemo.repository.episodicMemoryRepository import episodicMemoryRepository
from  minimemo.repository.originContentRepository import originContentRepository
from  minimemo.repository.semanticMemoryRepository import semanticMemoryRepository


def get_agent_repo(session: Session = Depends(get_session)) -> agentRepository:
    return agentRepository(session)


def get_origin_content_repo(
    session: Session = Depends(get_session),
) -> originContentRepository:
    return originContentRepository(session)


def get_embedding_repo(session: Session = Depends(get_session)) -> embeddingRepository:
    return embeddingRepository(session)


def get_episodic_memory_repo(
    session: Session = Depends(get_session),
) -> episodicMemoryRepository:
    return episodicMemoryRepository(session)


def get_semantic_memory_repo(
    session: Session = Depends(get_session),
) -> semanticMemoryRepository:
    return semanticMemoryRepository(session)
