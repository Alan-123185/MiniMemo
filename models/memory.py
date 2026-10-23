import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from db.Base import Base


class Memory(Base):
    __tablename__ = "memory"

    id:Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    content: Mapped[str]=mapped_column(nullable=False)
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    update_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    origin_content_id: Mapped[str|None] = mapped_column(ForeignKey("origin_content.id"), nullable=True)