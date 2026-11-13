import uuid
from typing import Any
from sqlalchemy import update
from common.memoryInfo import memoryInfo, semanticMemoryInfo
from models.memoryModel.semanticMemory import semanticMemory
from repository.memoryRepository import memoryRepository


class semanticMemoryRepository(memoryRepository[semanticMemoryInfo]):
    kind = "semantics"
    model = semanticMemory  #指定对应的ORM类

    def _alive_conditions(self) -> list[Any]:
        """
        语义记忆除了没被软删除，还要求这条事实当前仍然成立
        """
        return super()._alive_conditions() + [semanticMemory.is_alive.is_(True)]

    async def add_memory(
        self,
        memories: list[semanticMemoryInfo],  #多态访问 到时候传入semanticMemoryInfo
        agent_id: str,
        origin_content_id: str | None = None,
        commit: bool = True,
    ) -> None:
        """
        批量新增语义记忆，模型给出的 type / is_alive 一并落库
        """
        for memory in memories:
            memo = semanticMemory(
                id=str(uuid.uuid4()),
                content=memory.content,
                agent_id=agent_id,
                type=memory.type,
                is_alive=memory.is_alive,
            )
            await self._add_with_vector(memo, agent_id, memory)
        if commit:
            await self.session.commit()



    async def kill_memory(self, memory_id: str) -> None:
        """
        语义记忆的“作废”是双重语义：事实不再成立，同时也从检索中隐去
        """
        await self.session.execute(
            update(semanticMemory)
            .where(semanticMemory.id == memory_id)
            .values(is_alive=False)
            .execution_options(synchronize_session=False)
        )
        await super().kill_memory(memory_id)
