import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from  db.Base import Base


class Agent(Base):
    __tablename__ = "agents"

    # 内部主键，子表的 agent_id 外键、后台任务和锁都使用这个值。
    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    # 对外的 Agent 名称，只要求在同一个用户下唯一。
    agent_name: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "agent_name", name="uq_user_agent"),
    )
