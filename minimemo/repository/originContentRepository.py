from minimemo.models.memoryModel.memory import Memory
from minimemo.models.origin_content import originContent
from minimemo.repository.memoryRepository import memoryRepository


"""
原文仓库
原文也是记忆，继承结构与情景/语义一致，
所以增删改查全部复用基类，只有“新增”需要处理 additional_kwargs
"""


class originContentRepository(memoryRepository):
    kind = "origin_content"
    model = originContent

    def add_memory(
        self,
        memories: list[dict],
        agent_id: str
    ) -> None:
        """
        批量新增原文
        10.29  包含角色来源 会话id  I will crack
        """
        for memory in memories:
            memo = originContent(
                content=memory["content"],
                agent_id=agent_id,
                role=memory.get("role", "system"),
                session_id=memory.get("session_id","default")
            )
            self._add_with_vector(memo, agent_id, memory)
        self.session.commit()



    def search_content(self, content_ids: list[str]) -> list[Memory]:
        """
        按 id 列表召回原文，返回顺序与传入顺序一致
        """
        return self.search_memory(content_ids)
