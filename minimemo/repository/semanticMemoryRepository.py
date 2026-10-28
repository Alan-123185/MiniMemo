import uuid
from typing import Any

from minimemo.models.memoryModel.semanticMemory import semanticMemory
from minimemo.repository.memoryRepository import memoryRepository


class semanticMemoryRepository(memoryRepository):
    kind = "semantics"
    model = semanticMemory

    def _alive_conditions(self) -> list[Any]:
        """
        语义记忆除了没被软删除，还要求这条事实当前仍然成立
        """
        return super()._alive_conditions() + [semanticMemory.is_alive.is_(True)]

    def add_memory(
        self,
        memories: list[dict],
        agent_id: str,
        origin_content_id: str | None = None,
    ) -> None:
        """
        批量新增语义记忆，模型给出的 type / is_alive 一并落库
        """
        for memory in memories:
            memo = semanticMemory(
                id=str(uuid.uuid4()),
                content=memory["content"],
                agent_id=agent_id,
                type=memory.get("type") or "fact",
                is_alive=memory.get("is_alive", True),
            )
            self._add_with_vector(memo, agent_id, memory)
        self.session.commit()

    def kill_memory(self, memory_id: str) -> None:
        """
        语义记忆的“作废”是双重语义：事实不再成立，同时也从检索中隐去
        """
        self.session.query(semanticMemory).filter(
            semanticMemory.id == memory_id
        ).update({"is_alive": False}, synchronize_session=False)
        super().kill_memory(memory_id)
