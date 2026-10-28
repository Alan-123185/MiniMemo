from fastapi import Depends

from minimemo.repository.dependencies import (
    get_embedding_repo,
    get_episodic_memory_repo,
    get_origin_content_repo,
    get_semantic_memory_repo,
)
from minimemo.repository.embeddingRepository import embeddingRepository
from minimemo.repository.episodicMemoryRepository import episodicMemoryRepository
from minimemo.repository.originContentRepository import originContentRepository
from minimemo.repository.semanticMemoryRepository import semanticMemoryRepository
from  minimemo.service.memoryService import memoryService


def get_memory_service(
    embedding_repository: embeddingRepository = Depends(get_embedding_repo),
    episodic_memory_repository: episodicMemoryRepository = Depends(
        get_episodic_memory_repo
    ),
    semantic_memory_repository: semanticMemoryRepository = Depends(
        get_semantic_memory_repo
    ),
    origin_content_repository: originContentRepository = Depends(
        get_origin_content_repo
    ),
) -> memoryService:
    return memoryService(
        semantic_memory_repository=semantic_memory_repository,
        episodic_memory_repository=episodic_memory_repository,
        origin_content_repository=origin_content_repository,
        embedding_repository=embedding_repository,
    )
