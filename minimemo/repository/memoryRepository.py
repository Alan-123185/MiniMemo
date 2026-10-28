from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy.orm import Session

from minimemo.models.memoryModel.memory import Memory
from minimemo.models.memoryVector import memoryVector

"""
记忆仓库基类
增删改查的公共实现放在这里，子类只负责“新增”和“按类型召回”这两件事
"""


class memoryRepository:
    kind: str

    # 子类必须指定自己对应的 ORM 类
    model: type[Memory] = Memory

    def __init__(self, session: Session):
        self.session = session

    def _alive_conditions(self) -> list[Any]:
        """
        判定一条记忆是否“活着”的条件
        基类只有软删除标记，子类可以追加自己的条件
        """
        return [Memory.is_delete.is_(False)]

    def add_memory(
        self,
        memories: list[dict],
        agent_id: str,
        origin_content_id: str | None = None,
    ) -> None:
        """
        批量新增记忆，并同步写入对应的向量
        """
        raise NotImplementedError

    def search_memory(self, memory_ids: list[str]) -> list[Memory]:
        """
        按 id 列表召回记忆，返回顺序与传入顺序一致
        多路召回之后顺序本身就是有价值的信号，不能丢
        """
        if not memory_ids:
            return []
        rows = (
            self.session.query(self.model)
            .filter(self.model.id.in_(memory_ids), *self._alive_conditions())
            .all()
        )
        by_id = {row.id: row for row in rows}
        return [by_id[memory_id] for memory_id in memory_ids if memory_id in by_id]

    def remove_memory(self, memory_id: str) -> None:
        """
        物理删除一条记忆，连同向量一起清掉
        joined 继承下子表行和父表行是两条记录，
        只有交给 ORM 删对象才会把整条继承链一起清掉，
        query(...).delete() 只删子表那一行，父表会留下垃圾数据
        """
        memory = self.session.get(self.model, memory_id)
        if memory is None:
            return
        self.session.query(memoryVector).filter(
            memoryVector.memory_id == memory_id
        ).delete(synchronize_session=False)
        self.session.delete(memory)
        self.session.commit()

    def kill_memory(self, memory_id: str) -> None:
        """
        软删除一条记忆，只打标记不删数据
        """
        self.session.query(Memory).filter(Memory.id == memory_id).update(
            {
                "is_delete": True,
                "update_time": datetime.datetime.now(),
            },
            synchronize_session=False,
        )
        self.session.commit()

    def update_memory(self, memory_id: str, content: str, new_embedding: bytes) -> None:
        """
        更新记忆的内容与向量，大模型判定为 UPDATE 之后调用
        content 在父表 memory 上，查基类就能改到
        onupdate 只在 ORM flush 时生效，批量 update 需要手动写时间
        """
        self.session.query(Memory).filter(Memory.id == memory_id).update(
            {
                "content": content,
                "update_time": datetime.datetime.now(),
            },
            synchronize_session=False,
        )
        self.session.query(memoryVector).filter(
            memoryVector.memory_id == memory_id
        ).update({"embedding": new_embedding}, synchronize_session=False)
        self.session.commit()

    def _add_with_vector(self, memory: Memory, agent_id: str, payload: dict) -> None:
        """
        新增一条记忆并挂上向量
        """
        self.session.add(memory)
        # flush 一下拿到主键，再建向量
        self.session.flush()
        self.session.add(
            memoryVector(
                memory_id=memory.id,
                embedding=payload["embedding"],
                embedding_model=payload["embedding_model"],
                agent_id=agent_id,
            )
        )
