from fastapi.params import Depends

from repository.dependencies import get_origin_content_repo, get_memory_repo, get_embedding_repo
from service.memoryService import memoryService





def get_memory_service(embedding_repository=Depends(get_embedding_repo), memory_repository=Depends(get_memory_repo), origin_content_repository=Depends(get_origin_content_repo)) -> memoryService:
    return memoryService(
        memory_repository=memory_repository,
        origin_content_repository=origin_content_repository,
        embedding_repository=embedding_repository
    )


