import datetime
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from  minimemo.db.Base import Base


class originContent(Base):
   __tablename__ = "origin_content"

   id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
   agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
   content:Mapped[str] = mapped_column(nullable=False)
   additional_kwargs: Mapped[dict[str, Any] | None] = mapped_column(
      MutableDict.as_mutable(JSON)
   )
   create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now )
   update_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)