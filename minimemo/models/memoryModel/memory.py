import datetime
from typing import Literal
import uuid
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from  minimemo.db.Base import Base


class Memory(Base):
    __tablename__ = "memory"

    id:Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    content: Mapped[str]=mapped_column(nullable=False)
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    update_time: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(),
        onupdate=lambda: datetime.datetime.now(),
    )
    is_delete:Mapped[bool] = mapped_column(default=False, nullable=False)



    memory_type: Mapped[Literal["origin","episodic","semantic"]] = mapped_column(index=True)   # 鉴别器

    __mapper_args__ = {
        "polymorphic_on": "memory_type",
        "polymorphic_identity": "base",
    }

