from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from  db.session import get_session
from  repository.agentRepository import agentRepository
from  repository.embeddingRepository import embeddingRepository
from  repository.episodicMemoryRepository import episodicMemoryRepository
from  repository.originContentRepository import originContentRepository
from  repository.semanticMemoryRepository import semanticMemoryRepository
from repository.sessionRepository import sessionRepository


def get_agent_repo(session: AsyncSession = Depends(get_session)) -> agentRepository:
    return agentRepository(session)


def get_session_repo(session: AsyncSession = Depends(get_session)) -> sessionRepository:
    return sessionRepository(session)


def get_origin_content_repo(
    session: AsyncSession = Depends(get_session),
) -> originContentRepository:
    return originContentRepository(session)


def get_embedding_repo(session: AsyncSession = Depends(get_session)) -> embeddingRepository:
    return embeddingRepository(session)


def get_episodic_memory_repo(
    session: AsyncSession = Depends(get_session),
) -> episodicMemoryRepository:
    return episodicMemoryRepository(session)


def get_semantic_memory_repo(
    session: AsyncSession = Depends(get_session),
) -> semanticMemoryRepository:
    return semanticMemoryRepository(session)
