from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from minimemo.models.memoryModel.memory import Memory


"""
10.27 
大重构 拆分记忆
"""
class semanticMemory(Memory):

    __tablename__ = "semantics"

    id: Mapped[str] = mapped_column(ForeignKey("memory.id"), primary_key=True)
    type:Mapped[str] = mapped_column(nullable=False)
    is_alive:Mapped[bool] = mapped_column(default=True, nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "semantic",
    }


