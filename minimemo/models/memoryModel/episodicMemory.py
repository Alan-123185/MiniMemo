from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from minimemo.models.memoryModel.memory import Memory


"""
10.27 
大重构 拆分记忆
"""
class episodicMemory(Memory):
    __tablename__ = "episodes"

    origin_content_id: Mapped[str|None] = mapped_column(ForeignKey("origin_content.id"), nullable=True)
