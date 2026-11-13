
from common.unarchiveSessionStatus import unarchiveSessionStatus
from common.memoryInfo import memoryInfo, originContentMemoryInfo
from models.memoryModel.memory import Memory
from models.memoryModel.origin_content import originContent
from repository.memoryRepository import memoryRepository
from sqlalchemy import func, select, update


"""
原文仓库
原文也是记忆，继承结构与情景/语义一致，
所以增删改查全部复用基类，只有“新增”需要处理 additional_kwargs
"""


class originContentRepository(memoryRepository[originContentMemoryInfo]):
    kind = "origin_content"
    model = originContent

    async def add_memory(
        self,
        memories: list[originContentMemoryInfo],
        agent_id: str
    ) -> None:
        """
        批量新增原文
        10.29  包含角色来源 会话id  I will crack
        """
        for memory in memories:
            memo = originContent(
                content=memory.content,
                agent_id=agent_id,
                role=memory.role,
                session=memory.session_id,
                #默认没有被归档 不需要管它 不在这里更新
            )
            await self._add_with_vector(memo, agent_id, memory)
        await self.session.commit()



    async def search_content(self, content_ids: list[str]) -> list[Memory]:
        """
        按 id 列表召回原文，返回顺序与传入顺序一致
        """
        return await self.search_memory(content_ids)


    _unarchived_conditions = [
        originContent.is_delete.is_(False),
        originContent.is_archive.is_(False),
    ]




    async def get_unarchived_session_stats(self, agent_id: str) -> list[unarchiveSessionStatus]:
        """
        只取每个会话的未归档条数与最新落库时间  供水位判断用
        判断水位只需要这两个数字，没必要把原文正文整组拉出来
        返回 {session_id: (条数, 最新落库时间)}
        """
        rows=(await self.session.execute(
            select(
                originContent.session,
                func.count(originContent.id),
                func.max(originContent.create_time),
            ).where(
                originContent.agent_id == agent_id,
                *self._unarchived_conditions,
            ).group_by(originContent.session)
        )).all()
        return [unarchiveSessionStatus(session=row[0], count=row[1], the_latest_create_time=row[2]) for row in rows]



    async def fetch_unarchived_by_session(self, agent_id: str, session_id: str, limit: int | None = None) -> list[originContent]:
        """
        这个方法和上面的不一样，提供了会话id，可以灵活的按照会话取未归档原文
        limit=None 时不限量，供显式归档整段会话用
        """
        query = select(originContent).where(
            originContent.agent_id == agent_id,
            originContent.session == session_id,
            *self._unarchived_conditions,
        ).order_by(originContent.create_time.asc())
        if limit is not None:
            query = query.limit(limit)
        return (await self.session.execute(query)).scalars().all()




    async def mark_archived(self, content_ids: list[str], agent_id: str) -> None:
        """
        把一批原文标记为已归档，必须和 episodes 落库在同一个事务里提交
        这里为了确保原子性 更新了并未提交事务  后面会锁死
        """
        if not content_ids:
            return
        await self._require_owned_memories(content_ids, agent_id)
        await self.session.execute(
            update(originContent)
            .where(
                originContent.id.in_(content_ids),
                originContent.id.in_(select(Memory.id).where(Memory.agent_id == agent_id)),
            )
            .values(is_archive=True)
            .execution_options(synchronize_session=False)
        )
