import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.Base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "agent_name", name="uq_user_agent"),
    )
