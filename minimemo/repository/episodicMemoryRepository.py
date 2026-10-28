import uuid

from minimemo.models.memoryModel.episodicMemory import episodicMemory
from minimemo.repository.memoryRepository import memoryRepository


class episodicMemoryRepository(memoryRepository):
    kind = "episodes"
    model = episodicMemory

    def add_memory(
        self,
        memories: list[dict],
        agent_id: str,
        origin_content_id: str | None = None,
    ) -> None:
        """
        批量新增情景记忆
        """
        for memory in memories:
            memo = episodicMemory(
                id=str(uuid.uuid4()),
                content=memory["content"],
                agent_id=agent_id,
                origin_content_id=origin_content_id,
            )
            self._add_with_vector(memo, agent_id, memory)
        self.session.commit()
