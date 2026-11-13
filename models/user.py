from sqlalchemy.orm import Mapped, mapped_column

from db.Base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(primary_key=True)
