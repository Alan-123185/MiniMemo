

from minimemo.common.memoryInfo import memoryInfo, originContentMemoryInfo
from minimemo.models.memoryModel.memory import Memory
from minimemo.models.origin_content import originContent
from minimemo.repository.memoryRepository import memoryRepository


"""
原文仓库
原文也是记忆，继承结构与情景/语义一致，
所以增删改查全部复用基类，只有“新增”需要处理 additional_kwargs
"""


class originContentRepository(memoryRepository[originContentMemoryInfo]):
    kind = "origin_content"
    model = originContent

    def add_memory(
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
            self._add_with_vector(memo, agent_id, memory)
        self.session.commit()



    def search_content(self, content_ids: list[str]) -> list[Memory]:
        """
        按 id 列表召回原文，返回顺序与传入顺序一致
        """
        return self.search_memory(content_ids)


    _unarchived_conditions = [
        originContent.is_delete.is_(False),
        originContent.is_archive.is_(False),
    ]


    def get_not_archived_content(self, agent_id: str) -> list[originContent]:
        """
        获取指定智能体的所有未归档原文
        """
        return self.session.query(originContent).filter(
            originContent.agent_id == agent_id,
            *self._unarchived_conditions,
        ).all()


    # 未归档的公共过滤条件，水位查询与归档标记共用一套


    def fetch_unarchived(self, agent_id: str, session_id: str, limit: int | None = None) -> list[originContent]:
        """
        按时间正序取一个会话内未归档的原文
        limit=None 时不限量，供显式归档整段会话用
        """
        query = self.session.query(originContent).filter(
            originContent.agent_id == agent_id,
            originContent.session == session_id,
            *self._unarchived_conditions,
        ).order_by(originContent.create_time.asc())
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def mark_archived(self, content_ids: list[str]) -> None:
        """
        把一批原文标记为已归档，必须和 episodes 落库在同一个事务里提交
        这里为了确保原子性 更新了并未提交事务  后面会锁死
        """
        if not content_ids:
            return
        self.session.query(originContent).filter(
            originContent.id.in_(content_ids)
        ).update(
            {"is_archive": True},
            synchronize_session=False,
        )