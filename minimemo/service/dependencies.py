from fastapi.params import Depends

from  minimemo.repository.dependencies import get_origin_content_repo, get_memory_repo, get_embedding_repo
from minimemo.repository.embeddingRepository import embeddingRepository
from minimemo.repository.memoryRepository import memoryRepository
from minimemo.repository.originContentRepository import originContentRepository
from  minimemo.service.memoryService import memoryService







def get_memory_service(embedding_repository:embeddingRepository|None=None, memory_repository:memoryRepository|None=None, origin_content_repository:originContentRepository|None=None) -> memoryService:
    if embedding_repository is None:
        embedding_repository = get_embedding_repo()
    if memory_repository is None:
        memory_repository = get_memory_repo()
    if origin_content_repository is None:
        origin_content_repository = get_origin_content_repo()
    return memoryService(
        memory_repository=memory_repository,
        origin_content_repository=origin_content_repository,
        embedding_repository=embedding_repository
    )

