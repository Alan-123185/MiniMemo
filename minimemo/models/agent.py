from sqlalchemy.orm import Mapped, mapped_column
from  minimemo.db.Base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(primary_key=True)
