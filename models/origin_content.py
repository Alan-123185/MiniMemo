import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from db.Base import Base


class originContent(Base):
   __tablename__ = "origin_content"

   id:Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
   agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
   content:Mapped[str] = mapped_column(nullable=False)
   additional_kwargs: Mapped[dict[str, Any] | None] = mapped_column(
      MutableDict.as_mutable(JSON)
   )
   create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now )
   update_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)