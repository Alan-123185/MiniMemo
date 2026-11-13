from fastapi import Depends

from repository.dependencies import (
    get_embedding_repo,
    get_episodic_memory_repo,
    get_origin_content_repo,
    get_semantic_memory_repo,
)
from repository.embeddingRepository import embeddingRepository
from repository.episodicMemoryRepository import episodicMemoryRepository
from repository.originContentRepository import originContentRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from  service.memoryService import memoryService


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
