from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from minimemo.models.memoryModel.memory import Memory


"""
原文也是记忆的一种
content / agent_id / 时间 / is_delete 全部由父表 memory 提供，
这里只留原文特有的东西：
它不该参与检索，所以不放在 memory.content 上，而是单独一列。

这样 memory 表上的 memory_fts 索引和 memory_vector 向量表
天然就把原文一起覆盖了，不需要再为原文另开一套。
"""
class originContent(Memory):
    __tablename__ = "origin_content"

    id: Mapped[str] = mapped_column(ForeignKey("memory.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="system")  # 消息类型 用户还是智能体，系统
    session:Mapped[str] = mapped_column(nullable=True,default="default")  # 会话id
    __mapper_args__ = {
        "polymorphic_identity": "origin",
    }
