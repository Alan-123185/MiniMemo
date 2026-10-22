import datetime
import uuid

from sqlalchemy import LargeBinary, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from db.Base import Base


class memoryVector(Base):
    __tablename__ = "memory_vector"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_id :Mapped[str] = mapped_column(ForeignKey("memory.id"))
    embedding :Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # 核心：存 float32 的 raw bytes
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    embedding_model : Mapped[str] = mapped_column(nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"),nullable=False)