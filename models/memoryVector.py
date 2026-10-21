import datetime

from sqlalchemy import LargeBinary, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from db.Base import Base


class memoryVector(Base):
    __tablename__ = "memory_vector"

    id :Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_id :Mapped[str] = mapped_column(foreign_key="memory.id")
    embedding :Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # 核心：存 float32 的 raw bytes
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
