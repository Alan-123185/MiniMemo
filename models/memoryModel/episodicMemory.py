from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from models.memoryModel.memory import Memory


"""
10.27 
大重构 拆分记忆
"""
class episodicMemory(Memory):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(ForeignKey("memory.id"), primary_key=True)
    is_archive: Mapped[bool] = mapped_column(nullable=False,default=False)  # 是否归档进语义记忆

    __mapper_args__ = {
        "polymorphic_identity": "episodic",
    }
