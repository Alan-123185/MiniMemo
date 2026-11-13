import uuid

from sqlalchemy import func, select, update
from minimemo.common.memoryInfo import episodicMemoryInfo
from minimemo.common.unarchiveSessionStatus import unarchiveAgentStatus
from minimemo.models.episodeOriginLink import episodeOriginLink
from minimemo.models.memoryModel.episodicMemory import episodicMemory
from minimemo.repository.memoryRepository import memoryRepository

class episodicMemoryRepository(memoryRepository[episodicMemoryInfo]):
    kind = "episodes"
    model = episodicMemory



    _unarchived_conditions = [
        episodicMemory.is_delete.is_(False),
        episodicMemory.is_archive.is_(False),
    ]
        



    async def get_unarchived_agent_stats(self) -> list[unarchiveAgentStatus]:
        """
        仿照orginContentRepository获取所有未归档的智能体状态
        """
        rows=(await self.session.execute(
            select(
                episodicMemory.agent_id,
                func.count(episodicMemory.id),
                func.max(episodicMemory.create_time),
            ).where(
                *self._unarchived_conditions,
            ).group_by(episodicMemory.agent_id)
        )).all()
        return [unarchiveAgentStatus(agent=row[0], count=row[1], the_latest_create_time=row[2]) for row in rows]




    async def fetch_unarchived_by_agent(self, agent_id: str) -> list[episodicMemory]:
        """
        获取指定智能体的所有未归档原文  直接返回按照会话分组的字典 方便
        """
        episodic_memory_list=(await self.session.execute(
            select(episodicMemory).where(
                episodicMemory.agent_id == agent_id,
                *self._unarchived_conditions,
            ).order_by(episodicMemory.create_time.asc())
        )).scalars().all()
        #按会话拆分，每个会话各自攒各自的水位
        return episodic_memory_list





    async def add_memory(
        self,
        memories: list[episodicMemoryInfo],
        agent_id: str,
        origin_content_ids: dict[str, str] | None = None,
        commit: bool = True,
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
            await self._add_with_vector(memo, agent_id, memory)
            # 编号映射存在才建溯源边，LLM 没报或报了不存在的编号就跳过
            if origin_content_ids and memory.origin_content_id:
                for number in memory.origin_content_id:
                    content_id = origin_content_ids.get(str(number))
                    if content_id is not None:
                        self.session.add(episodeOriginLink(
                            episode_id=memo.id,
                            origin_content_id=content_id,
                        ))
        if commit:
            await self.session.commit()



    async def mark_archived(self, content_ids: list[str]) -> None:
            """
            把一批原文标记为已归档，必须和 episodes 落库在同一个事务里提交
            这里为了确保原子性 更新了并未提交事务  后面会锁死
            """
            if not content_ids:
                return
            await self.session.execute(
                update(episodicMemory)
                .where(episodicMemory.id.in_(content_ids))
                .values(is_archive=True)
                .execution_options(synchronize_session=False)
            )
