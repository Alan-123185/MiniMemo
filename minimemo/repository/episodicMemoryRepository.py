import uuid

from minimemo.common.memoryInfo import episodicMemoryInfo
from minimemo.models.episodeOriginLink import episodeOriginLink
from minimemo.models.memoryModel.episodicMemory import episodicMemory
from minimemo.repository.memoryRepository import memoryRepository


class episodicMemoryRepository(memoryRepository[episodicMemoryInfo]):
    kind = "episodes"
    model = episodicMemory

    def add_memory(
        self,
        memories: list[episodicMemoryInfo],
        agent_id: str,
        origin_content_ids: dict[str, str] | None = None,
    ) -> None:
        """
        批量新增情景记忆
        origin_content_ids 是编号到原文id的映射，
        memory.origin_content_id 里放的是 LLM 输出的编号，落库时换回真实id写入关联表
        """
        for memory in memories:
            memo = episodicMemory(
                id=str(uuid.uuid4()),
                content=memory.content,
                agent_id=agent_id,
            )
            self._add_with_vector(memo, agent_id, memory)
            # 编号映射存在才建溯源边，LLM 没报或报了不存在的编号就跳过
            if origin_content_ids and memory.origin_content_id:
                for number in memory.origin_content_id:
                    content_id = origin_content_ids.get(str(number))
                    if content_id is not None:
                        self.session.add(episodeOriginLink(
                            episode_id=memo.id,
                            origin_content_id=content_id,
                        ))
        self.session.commit()
