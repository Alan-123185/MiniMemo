from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from minimemo.models.memoryModel.memory import Memory


"""
10.27 
大重构 拆分记忆
"""
class episodicMemory(Memory):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(ForeignKey("memory.id"), primary_key=True)
    origin_content_id: Mapped[str|None] = mapped_column(ForeignKey("origin_content.id"), nullable=True)
    is_archive: Mapped[bool] = mapped_column(nullable=False,default=False)  # 是否归档进语义记忆

    __mapper_args__ = {
        "polymorphic_identity": "episodic",
    }
